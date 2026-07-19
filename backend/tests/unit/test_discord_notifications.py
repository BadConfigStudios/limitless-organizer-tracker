from datetime import datetime, timezone

from app.db.models import ApplicationStatus
from app.notifications.discord import (
    build_reminder_message,
    build_resubmission_message,
    build_status_update_message,
)


def test_build_resubmission_message_for_success():
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    message = build_resubmission_message(timestamp, success=True)

    assert "2026-06-12T09:00:00+00:00" in message
    assert "succeeded" in message.lower()


def test_build_resubmission_message_for_failure():
    timestamp = datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc)

    message = build_resubmission_message(timestamp, success=False)

    assert "2026-06-12T21:00:00+00:00" in message
    assert "failed" in message.lower()


def test_build_status_update_message_includes_status_and_timestamp():
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    message = build_status_update_message(ApplicationStatus.APPROVED, timestamp)

    assert "2026-06-12T09:00:00+00:00" in message
    assert "approved" in message.lower()


def test_build_reminder_message_includes_timestamp_and_prompts_manual_action():
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    message = build_reminder_message(timestamp)

    assert "2026-06-12T09:00:00+00:00" in message
    assert "resubmit" in message.lower()
