import httpx
import respx

import app.tasks.resubmit_tasks as resubmit_tasks
from app.celery_app import celery_app
from app.db.models import EventLog

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


def test_resubmit_reminder_task_does_not_perform_resubmission(monkeypatch, db_session_factory):
    """The reminder task must never call authenticated_page/resubmit_application (no auto-resubmit, #152)."""
    monkeypatch.setattr("app.db.session.SessionLocal", db_session_factory)
    monkeypatch.setattr(resubmit_tasks.settings, "discord_webhook_url", "")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("resubmit_reminder_task must not perform an actual resubmission")

    monkeypatch.setattr(resubmit_tasks, "authenticated_page", _fail_if_called)

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    resubmit_tasks.resubmit_reminder_task.delay()
