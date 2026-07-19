from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.db.models import ResubmissionEvent
from app.db.session import task_session
from app.events import log_event
from app.notifications.discord import post_reminder_notice, post_resubmission_notice
from app.scraper.browser import LoginFailed
from app.scraper.resubmit import resubmit_application
from app.scraper.session import authenticated_page


def record_resubmission(
    session: Session, success: bool, submitted_at: datetime, discord_notified: bool
) -> ResubmissionEvent:
    """Insert a resubmission datapoint (FR5)."""
    event = ResubmissionEvent(
        submitted_at=submitted_at, success=success, discord_notified=discord_notified
    )
    session.add(event)
    session.commit()
    return event


@celery_app.task(name="app.tasks.resubmit_tasks.resubmit_application_task")
def resubmit_application_task() -> int:
    """Resubmit the organization application and record the outcome (FR3, FR5).

    Posts a Discord notification with the outcome (FR4); the outcome is
    recorded (FR5) even if the notification fails. Returns the
    ResubmissionEvent row ID.
    """
    try:
        with authenticated_page() as ctx:
            result = resubmit_application(ctx.page)
            if settings.scraper_debug:
                if result.page_html is not None:
                    debug_html = result.page_html[:20000]
                else:
                    try:
                        debug_html = ctx.page.content()[:20000]
                    except Exception:
                        debug_html = None
            else:
                debug_html = None
    except LoginFailed:
        submitted_at = datetime.now(timezone.utc)
        with task_session() as session:
            event = record_resubmission(session, False, submitted_at, False)
            log_event(
                session=session,
                event_type="scraper.resubmit",
                source="resubmit_tasks",
                message="Application resubmission failed: incorrect credentials",
                severity="WARNING",
                details={"success": False, "failure_stage": "login", "event_id": event.id},
            )
            session.commit()
            return event.id
    submitted_at = datetime.now(timezone.utc)

    discord_notified = False
    try:
        response = post_resubmission_notice(settings.discord_webhook_url, submitted_at, result.success)
        discord_notified = response.status_code < 300
    except httpx.HTTPError:
        discord_notified = False

    with task_session() as session:
        event = record_resubmission(session, result.success, submitted_at, discord_notified)
        details = {
            "success": result.success,
            "discord_notified": discord_notified,
            "event_id": event.id,
        }
        if not result.success:
            details["failure_stage"] = result.failure_stage
            details["page_html"] = result.page_html
        if result.server_response:
            details["server_response"] = result.server_response
        if debug_html is not None:
            details["debug_page_html"] = debug_html
        log_event(
            session=session,
            event_type="scraper.resubmit",
            source="resubmit_tasks",
            message=f"Application resubmission {'succeeded' if result.success else 'failed'}"
            + (f" at stage: {result.failure_stage}" if result.failure_stage else ""),
            severity="INFO" if result.success else "WARNING",
            details=details,
        )
        session.commit()
        return event.id


@celery_app.task(name="app.tasks.resubmit_tasks.resubmit_reminder_task")
def resubmit_reminder_task() -> None:
    """Post a Discord reminder to resubmit the application manually (#152).

    Replaces the previous scheduled auto-resubmission (FR3): no login,
    scraping, or resubmission is performed here, only a reminder notice.
    """
    reminded_at = datetime.now(timezone.utc)

    discord_notified = False
    try:
        response = post_reminder_notice(settings.discord_webhook_url, reminded_at)
        discord_notified = response.status_code < 300
    except httpx.HTTPError:
        discord_notified = False

    with task_session() as session:
        log_event(
            session=session,
            event_type="scraper.resubmit_reminder",
            source="resubmit_tasks",
            message="Resubmission reminder sent",
            severity="INFO",
            details={"discord_notified": discord_notified},
        )
        session.commit()
