"""Unit tests for Celery task lifecycle signal handlers."""

import json
from unittest.mock import MagicMock, patch

from app.db.models import EventLog
from app.celery_signals import on_beat_init, on_task_prerun, on_task_postrun, on_task_failure


def test_on_task_prerun_logs_started_event(db_session_factory):
    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_task_prerun(
            sender=MagicMock(__name__="ingest_tournaments_task"),
            task_id="abc-123",
        )

    with db_session_factory() as session:
        row = session.query(EventLog).one()
        assert row.event_type == "task.started"
        assert row.severity == "INFO"
        assert row.source == "celery"
        assert row.correlation_id == "abc-123"
        assert "ingest_tournaments_task" in row.message


def test_on_task_postrun_logs_completed_event(db_session_factory):
    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_task_prerun(
            sender=MagicMock(__name__="ingest_tournaments_task"),
            task_id="abc-123",
        )
        on_task_postrun(
            sender=MagicMock(__name__="ingest_tournaments_task"),
            task_id="abc-123",
            retval=42,
        )

    with db_session_factory() as session:
        rows = session.query(EventLog).order_by(EventLog.id).all()
        assert len(rows) == 2
        completed = rows[1]
        assert completed.event_type == "task.completed"
        assert completed.severity == "INFO"
        assert completed.correlation_id == "abc-123"
        details = json.loads(completed.details)
        assert "duration_ms" in details
        assert details["result"] == "42"


def test_on_task_failure_logs_error_event(db_session_factory):
    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_task_prerun(
            sender=MagicMock(__name__="ingest_tournaments_task"),
            task_id="abc-123",
        )
        on_task_failure(
            sender=MagicMock(__name__="ingest_tournaments_task"),
            task_id="abc-123",
            exception=ValueError("something broke"),
            traceback=None,
        )

    with db_session_factory() as session:
        rows = session.query(EventLog).order_by(EventLog.id).all()
        assert len(rows) == 2
        failed = rows[1]
        assert failed.event_type == "task.failed"
        assert failed.severity == "ERROR"
        assert failed.correlation_id == "abc-123"
        details = json.loads(failed.details)
        assert "duration_ms" in details
        assert "something broke" in details["error"]


def test_on_task_postrun_without_prerun_still_works(db_session_factory):
    """postrun should not crash if prerun wasn't recorded (e.g., signal race)."""
    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_task_postrun(
            sender=MagicMock(__name__="some_task"),
            task_id="no-prerun",
            retval="ok",
        )

    with db_session_factory() as session:
        row = session.query(EventLog).one()
        assert row.event_type == "task.completed"
        details = json.loads(row.details)
        assert details["duration_ms"] is None


def test_signal_handlers_never_raise():
    """Signal handlers should swallow exceptions to never crash a task."""
    on_task_prerun(sender=MagicMock(__name__="t"), task_id="x")
    on_task_postrun(sender=MagicMock(__name__="t"), task_id="x", retval=None)
    on_task_failure(
        sender=MagicMock(__name__="t"),
        task_id="x",
        exception=RuntimeError("boom"),
        traceback=None,
    )


# --- on_beat_init ---


@patch("app.celery_app.build_beat_schedule")
@patch("app.config_db.get_effective_config")
def test_on_beat_init_calls_build_beat_schedule_with_effective_config(
    mock_get_config, mock_build, db_session_factory
):
    mock_get_config.return_value = {"key": "value"}
    sender = MagicMock()

    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_beat_init(sender=sender)

    mock_get_config.assert_called_once()
    mock_build.assert_called_once_with(sender.app, {"key": "value"})


@patch("app.celery_app.build_beat_schedule")
@patch("app.config_db.get_effective_config", side_effect=Exception("DB down"))
def test_on_beat_init_falls_back_to_env_defaults_when_db_unreachable(
    mock_get_config, mock_build, db_session_factory
):
    sender = MagicMock()

    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_beat_init(sender=sender)

    mock_build.assert_called_once()
    config_arg = mock_build.call_args[0][1]
    from app.config import settings
    assert config_arg["application_status_check_interval_hours"] == settings.application_status_check_interval_hours
    assert config_arg["resubmit_times_utc"] == settings.resubmit_times_utc


@patch("app.celery_app.build_beat_schedule", side_effect=Exception("Redis down"))
@patch("app.config_db.get_effective_config")
def test_on_beat_init_does_not_crash_when_redis_unavailable(
    mock_get_config, mock_build, db_session_factory
):
    mock_get_config.return_value = {"key": "value"}
    sender = MagicMock()

    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_beat_init(sender=sender)


@patch("app.celery_app.build_beat_schedule", side_effect=Exception("Redis down"))
@patch("app.config_db.get_effective_config")
def test_on_beat_init_logs_visible_event_when_schedule_rebuild_fails(
    mock_get_config, mock_build, db_session_factory
):
    """A failed startup rebuild must be visible in the app's own event log (#152),
    not just the celery-beat process logger — otherwise a stale schedule (e.g. one
    still auto-dispatching a task the operator believes was walked back) can persist
    silently after a deploy."""
    from app.db.models import EventLog

    mock_get_config.return_value = {"key": "value"}
    sender = MagicMock()

    with patch("app.celery_signals.SessionLocal", db_session_factory):
        on_beat_init(sender=sender)

    with db_session_factory() as session:
        events = session.query(EventLog).filter(
            EventLog.event_type == "beat.schedule_rebuild_failed"
        ).all()
        assert len(events) == 1
        assert events[0].severity == "ERROR"
