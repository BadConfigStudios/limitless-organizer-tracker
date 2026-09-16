from datetime import datetime, timezone

import httpx
import respx

from app.db.models import ApplicationStatus
from app.notifications.discord import (
    post_reminder_notice,
    post_resubmission_notice,
    post_status_update_notice,
)

WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"


@respx.mock
def test_post_resubmission_notice_posts_message_to_webhook():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    response = post_resubmission_notice(WEBHOOK_URL, timestamp, success=True)

    assert response.status_code == 204
    assert route.called
    payload = route.calls.last.request.content.decode()
    assert "2026-06-12T09:00:00+00:00" in payload
    assert "succeeded" in payload.lower()


@respx.mock
def test_post_status_update_notice_posts_message_to_webhook():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    response = post_status_update_notice(WEBHOOK_URL, ApplicationStatus.APPROVED, timestamp)

    assert response.status_code == 204
    assert route.called
    payload = route.calls.last.request.content.decode()
    assert "2026-06-12T09:00:00+00:00" in payload
    assert "approved" in payload.lower()


@respx.mock
def test_post_reminder_notice_posts_message_to_webhook():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    response = post_reminder_notice(WEBHOOK_URL, timestamp)

    assert response.status_code == 204
    assert route.called
    payload = route.calls.last.request.content.decode()
    assert "2026-06-12T09:00:00+00:00" in payload
    assert "resubmit" in payload.lower()


@respx.mock
def test_post_reminder_notice_includes_link_when_provided():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    response = post_reminder_notice(WEBHOOK_URL, timestamp, link="https://limitless-org-dashboard.badconfig.com")

    assert response.status_code == 204
    payload = route.calls.last.request.content.decode()
    assert "https://limitless-org-dashboard.badconfig.com" in payload


@respx.mock
def test_post_reminder_notice_omits_link_when_not_provided():
    route = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
    timestamp = datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)

    post_reminder_notice(WEBHOOK_URL, timestamp)

    payload = route.calls.last.request.content.decode()
    assert "http" not in payload.lower()
