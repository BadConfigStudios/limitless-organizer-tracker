"""Integration tests for the admin API router (FR20-FR23, FR27)."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from app.db.models import ConfigEntry, EventLog


def _seed_events(session_factory, count=5):
    with session_factory() as session:
        for i in range(count):
            session.add(EventLog(
                timestamp=datetime(2026, 6, 22, 12, i, 0, tzinfo=timezone.utc),
                event_type="task.completed" if i % 2 == 0 else "task.started",
                severity="INFO",
                source="celery",
                message=f"Event {i}",
                details=json.dumps({"index": i}),
                correlation_id=f"task-{i}",
            ))
        session.commit()


# --- GET /api/admin/event-log ---


def test_get_event_log_returns_paginated_events(client):
    test_client, session_factory = client
    _seed_events(session_factory, 5)

    response = test_client.get("/api/admin/event-log")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 5
    assert body["items"][0]["message"] == "Event 4"


def test_get_event_log_respects_limit_and_offset(client):
    test_client, session_factory = client
    _seed_events(session_factory, 10)

    response = test_client.get("/api/admin/event-log?limit=3&offset=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 10
    assert len(body["items"]) == 3
    assert body["limit"] == 3
    assert body["offset"] == 2


def test_get_event_log_filters_by_event_type(client):
    test_client, session_factory = client
    _seed_events(session_factory, 6)

    response = test_client.get("/api/admin/event-log?event_type=task.completed")
    assert response.status_code == 200
    body = response.json()
    assert all(item["event_type"] == "task.completed" for item in body["items"])


def test_get_event_log_filters_by_severity(client):
    test_client, session_factory = client
    with session_factory() as session:
        session.add(EventLog(
            timestamp=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            event_type="task.failed",
            severity="ERROR",
            source="celery",
            message="Failure",
        ))
        session.add(EventLog(
            timestamp=datetime(2026, 6, 22, 12, 1, 0, tzinfo=timezone.utc),
            event_type="task.completed",
            severity="INFO",
            source="celery",
            message="Success",
        ))
        session.commit()

    response = test_client.get("/api/admin/event-log?severity=ERROR")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "ERROR"


def test_get_event_log_filters_by_source(client):
    test_client, session_factory = client
    with session_factory() as session:
        session.add(EventLog(
            timestamp=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            event_type="scraper.status_check",
            severity="INFO",
            source="status_tasks",
            message="Status check",
        ))
        session.add(EventLog(
            timestamp=datetime(2026, 6, 22, 12, 1, 0, tzinfo=timezone.utc),
            event_type="task.completed",
            severity="INFO",
            source="celery",
            message="Task done",
        ))
        session.commit()

    response = test_client.get("/api/admin/event-log?source=status_tasks")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["source"] == "status_tasks"


def test_get_event_log_returns_details_as_json(client):
    test_client, session_factory = client
    with session_factory() as session:
        session.add(EventLog(
            timestamp=datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc),
            event_type="task.completed",
            severity="INFO",
            source="celery",
            message="Done",
            details=json.dumps({"count": 42}),
        ))
        session.commit()

    response = test_client.get("/api/admin/event-log")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["details"] == {"count": 42}


def test_get_event_log_empty_table(client):
    test_client, _ = client
    response = test_client.get("/api/admin/event-log")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


# --- GET /api/admin/diagnostics ---


def test_get_diagnostics_returns_health_fields(client):
    test_client, _ = client

    with patch("app.api.routers.admin.check_db_health") as mock_db, \
         patch("app.api.routers.admin.check_redis_health") as mock_redis, \
         patch("app.api.routers.admin.check_celery_workers") as mock_workers, \
         patch("app.api.routers.admin.check_beat_health") as mock_beat, \
         patch("app.api.routers.admin.get_last_success_per_task") as mock_last:
        mock_db.return_value = True
        mock_redis.return_value = True
        mock_workers.return_value = ["worker1"]
        mock_beat.return_value = True
        mock_last.return_value = {"ingest_tournaments_task": "2026-06-22T12:00:00+00:00"}

        response = test_client.get("/api/admin/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["db_ok"] is True
    assert body["redis_ok"] is True
    assert body["celery_workers"] == ["worker1"]
    assert body["beat_ok"] is True
    assert "ingest_tournaments_task" in body["last_success_per_task"]


# --- GET /api/admin/config ---


def test_get_config_returns_non_sensitive_settings(client):
    test_client, _ = client

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    body = response.json()

    assert "application_status_check_interval_hours" in body
    assert "tournament_ingest_interval_hours" in body
    assert "tournament_ingest_limit" in body
    assert "tournament_backfill_months" in body
    assert "organizer_scan_interval_hours" in body
    assert "organizer_scan_limit" in body
    assert "resubmit_times_utc" in body
    assert "display_timezone" in body


def test_get_config_excludes_sensitive_fields(client):
    test_client, _ = client

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    body = response.json()

    assert "database_url" not in body
    assert "celery_broker_url" not in body
    assert "celery_result_backend" not in body
    assert "limitless_username" not in body
    assert "limitless_password" not in body
    assert "discord_webhook_url" not in body
    assert "api_keys" not in body


# --- GET /api/admin/tasks ---


def test_get_tasks_returns_task_list(client):
    test_client, _ = client

    response = test_client.get("/api/admin/tasks")
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body, list)
    assert len(body) >= 4

    names = {t["name"] for t in body}
    assert "ingest_tournaments" in names
    assert "scan_organizers" in names
    assert "check_application_status" in names
    # Resubmission is no longer surfaced via the Admin panel (#152) — it's a
    # deliberate user action via the "Resubmit Now" button on My Application.
    assert "resubmit_application" not in names

    for task in body:
        assert "name" in task
        assert "endpoint" in task
        assert "method" in task
        assert "description" in task
        assert "component" in task


# --- GET /api/admin/config — FR27: DB-merged effective config ---


def test_get_config_returns_db_overrides(client):
    """FR27: DB entries override env-var defaults in GET /api/admin/config."""
    test_client, session_factory = client
    with session_factory() as session:
        session.add(ConfigEntry(
            key="tournament_ingest_limit",
            value="42",
            updated_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
        ))
        session.add(ConfigEntry(
            key="organizer_scan_limit",
            value="200",
            updated_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
        ))
        session.commit()

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    body = response.json()
    assert body["tournament_ingest_limit"] == 42
    assert body["organizer_scan_limit"] == 200


def test_get_config_returns_defaults_for_non_overridden_keys(client):
    """FR27: keys without DB entries still return settings defaults."""
    test_client, session_factory = client
    with session_factory() as session:
        session.add(ConfigEntry(
            key="tournament_ingest_limit",
            value="42",
            updated_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
        ))
        session.commit()

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    body = response.json()
    assert body["tournament_ingest_limit"] == 42
    from app.config import settings
    assert body["tournament_backfill_months"] == settings.tournament_backfill_months


# --- PUT /api/admin/config — FR28: admin config editing ---


def test_put_config_updates_single_key(client):
    """FR28: PUT with a single key persists the override and returns effective config."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={"tournament_ingest_limit": 42},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tournament_ingest_limit"] == 42


def test_put_config_updates_multiple_keys(client):
    """FR28: PUT with multiple keys persists all overrides."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={
            "tournament_ingest_limit": 99,
            "organizer_scan_limit": 500,
            "resubmit_times_utc": "10:00,22:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tournament_ingest_limit"] == 99
    assert body["organizer_scan_limit"] == 500
    assert body["resubmit_times_utc"] == "10:00,22:00"


def test_put_config_returns_full_effective_config(client):
    """FR28: PUT response includes all config keys, not just the ones updated."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={"tournament_ingest_limit": 42},
    )
    assert response.status_code == 200
    body = response.json()
    assert "application_status_check_interval_hours" in body
    assert "resubmit_times_utc" in body
    assert "organizer_scan_limit" in body
    assert "organizer_scan_start_id" in body


def test_put_config_rejects_non_editable_key(client):
    """FR28: keys outside the allowlist are rejected with 422."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={"database_url": "postgres://evil"},
    )
    assert response.status_code == 422


def test_put_config_rejects_empty_body(client):
    """FR28: empty update dict is rejected with 422."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={},
    )
    assert response.status_code == 422


def test_put_config_persists_across_get(client):
    """FR28: values written via PUT are returned by subsequent GET."""
    test_client, _ = client

    test_client.put(
        "/api/admin/config",
        json={"tournament_ingest_limit": 77},
    )

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    assert response.json()["tournament_ingest_limit"] == 77


def test_put_config_validates_int_type(client):
    """FR28: string values for int fields are rejected with 422."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={"tournament_ingest_limit": "not_a_number"},
    )
    assert response.status_code == 422


# --- PUT /api/admin/config — FR29: beat schedule rebuild ---


def test_put_config_rebuilds_beat_schedule(client):
    """FR29: PUT /api/admin/config triggers build_beat_schedule() after persisting changes."""
    test_client, _ = client

    with patch("app.api.routers.admin.build_beat_schedule") as mock_build:
        response = test_client.put(
            "/api/admin/config",
            json={"tournament_ingest_limit": 42},
        )

    assert response.status_code == 200
    mock_build.assert_called_once()


def test_put_config_rebuild_receives_updated_config(client):
    """FR29: build_beat_schedule() is called with the effective config after DB writes."""
    test_client, _ = client

    with patch("app.api.routers.admin.build_beat_schedule") as mock_build:
        test_client.put(
            "/api/admin/config",
            json={"resubmit_times_utc": "10:00,22:00"},
        )

    config_arg = mock_build.call_args[0][1]
    assert config_arg["resubmit_times_utc"] == "10:00,22:00"


def test_put_config_logs_event_when_rebuild_fails(client):
    """FR29: failed schedule rebuild logs a warning event visible in the admin UI."""
    test_client, session_factory = client

    with patch(
        "app.api.routers.admin.build_beat_schedule",
        side_effect=Exception("Redis down"),
    ):
        response = test_client.put(
            "/api/admin/config",
            json={"tournament_ingest_limit": 42},
        )

    assert response.status_code == 200

    with session_factory() as session:
        from app.db.models import EventLog

        row = session.query(EventLog).filter_by(
            event_type="config.schedule_rebuild_failed"
        ).one()
        assert row.severity == "WARNING"
        assert "stale" in row.message


# --- FR30: display_timezone config key ---


def test_get_config_returns_display_timezone_default(client):
    """FR30: display_timezone should default to America/Chicago."""
    test_client, _ = client

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    assert response.json()["display_timezone"] == "America/Chicago"


def test_put_config_updates_display_timezone(client):
    """FR30: display_timezone is editable via PUT /api/admin/config."""
    test_client, _ = client

    response = test_client.put(
        "/api/admin/config",
        json={"display_timezone": "America/New_York"},
    )
    assert response.status_code == 200
    assert response.json()["display_timezone"] == "America/New_York"


def test_put_config_display_timezone_persists_across_get(client):
    """FR30: display_timezone set via PUT is returned by subsequent GET."""
    test_client, _ = client

    test_client.put(
        "/api/admin/config",
        json={"display_timezone": "Europe/London"},
    )

    response = test_client.get("/api/admin/config")
    assert response.status_code == 200
    assert response.json()["display_timezone"] == "Europe/London"
