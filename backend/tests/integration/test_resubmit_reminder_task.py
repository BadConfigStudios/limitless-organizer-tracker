import httpx
import respx

import app.tasks.resubmit_tasks as resubmit_tasks
from app.celery_app import celery_app
from app.db.models import EventLog, ResubmissionEvent

WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"


@respx.mock
def test_resubmit_reminder_task_posts_discord_notice_and_logs_event(monkeypatch, db_session_factory):
    monkeypatch.setattr("app.db.session.SessionLocal", db_session_factory)
    monkeypatch.setattr(resubmit_tasks.settings, "discord_webhook_url", WEBHOOK_URL)

    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    resubmit_tasks.resubmit_reminder_task.delay()

    assert route.called
    payload = route.calls.last.request.content.decode()
    assert "resubmit" in payload.lower()

    with db_session_factory() as session:
        events = session.query(EventLog).filter(EventLog.event_type == "scraper.resubmit_reminder").all()
        assert len(events) == 1
        assert events[0].severity == "INFO"


@respx.mock
def test_resubmit_reminder_task_includes_dashboard_link_when_configured(monkeypatch, db_session_factory):
    monkeypatch.setattr("app.db.session.SessionLocal", db_session_factory)
    monkeypatch.setattr(resubmit_tasks.settings, "discord_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(resubmit_tasks.settings, "dashboard_base_url", "https://limitless-org-dashboard.badconfig.com")

    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    resubmit_tasks.resubmit_reminder_task.delay()

    payload = route.calls.last.request.content.decode()
    assert "https://limitless-org-dashboard.badconfig.com" in payload


def test_resubmit_reminder_task_does_not_perform_resubmission(monkeypatch, db_session_factory):
    """The reminder task must never perform an actual resubmission (no auto-resubmit, #152).

    Patches every entry point resubmit_application_task uses to reach the scraper
    (authenticated_page, resubmit_application) so a future refactor that routes the
    reminder through any of them fails loudly, and additionally asserts no
    ResubmissionEvent row is created — the outcome-level invariant, independent of
    which internal function would have been called.
    """
    monkeypatch.setattr("app.db.session.SessionLocal", db_session_factory)
    monkeypatch.setattr(resubmit_tasks.settings, "discord_webhook_url", "")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("resubmit_reminder_task must not perform an actual resubmission")

    monkeypatch.setattr(resubmit_tasks, "authenticated_page", _fail_if_called)
    monkeypatch.setattr(resubmit_tasks, "resubmit_application", _fail_if_called)
    monkeypatch.setattr(resubmit_tasks, "record_resubmission", _fail_if_called)

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    resubmit_tasks.resubmit_reminder_task.delay()

    with db_session_factory() as session:
        assert session.query(ResubmissionEvent).count() == 0
