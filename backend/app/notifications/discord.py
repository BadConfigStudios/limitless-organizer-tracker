from datetime import datetime

import httpx

from app.db.models import ApplicationStatus

_SUCCESS_TEMPLATE = "Resubmission succeeded at {timestamp}."
_FAILURE_TEMPLATE = "Resubmission failed at {timestamp}."
_STATUS_UPDATE_TEMPLATE = "Application status changed to {status} at {timestamp}."
_REMINDER_TEMPLATE = (
    "Reminder ({timestamp}): time to resubmit the organization application. "
    "Use the Resubmit Now button on the dashboard's My Application tab."
)


def build_resubmission_message(timestamp: datetime, success: bool) -> str:
    """Build the Discord message content for a resubmission event."""
    template = _SUCCESS_TEMPLATE if success else _FAILURE_TEMPLATE
    return template.format(timestamp=timestamp.isoformat())


def post_resubmission_notice(webhook_url: str, timestamp: datetime, success: bool) -> httpx.Response:
    """Post a Discord notification for a resubmission event via webhook."""
    message = build_resubmission_message(timestamp, success)
    return httpx.post(webhook_url, json={"content": message})


def build_status_update_message(status: ApplicationStatus, timestamp: datetime) -> str:
    """Build the Discord message content for an application status change."""
    return _STATUS_UPDATE_TEMPLATE.format(status=status.value, timestamp=timestamp.isoformat())


def post_status_update_notice(
    webhook_url: str, status: ApplicationStatus, timestamp: datetime
) -> httpx.Response:
    """Post a Discord notification for an application status change via webhook."""
    message = build_status_update_message(status, timestamp)
    return httpx.post(webhook_url, json={"content": message})


def build_reminder_message(timestamp: datetime) -> str:
    """Build the Discord message content for a resubmission reminder."""
    return _REMINDER_TEMPLATE.format(timestamp=timestamp.isoformat())


def post_reminder_notice(webhook_url: str, timestamp: datetime) -> httpx.Response:
    """Post a Discord notification reminding the user to resubmit manually."""
    message = build_reminder_message(timestamp)
    return httpx.post(webhook_url, json={"content": message})
