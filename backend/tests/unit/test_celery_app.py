from datetime import timedelta
from unittest.mock import MagicMock, patch

from celery.schedules import crontab

from app.celery_app import _hourly_schedule, build_schedule_entries, parse_resubmit_times


def test_parse_resubmit_times_parses_multiple_times():
    assert parse_resubmit_times("09:00,21:00") == [(9, 0), (21, 0)]


def test_parse_resubmit_times_strips_whitespace():
    assert parse_resubmit_times(" 09:00 , 21:00 ") == [(9, 0), (21, 0)]


def test_parse_resubmit_times_empty_string_returns_no_times():
    assert parse_resubmit_times("") == []


def test_parse_resubmit_times_skips_blank_entries():
    assert parse_resubmit_times("09:00,,21:00,") == [(9, 0), (21, 0)]


def test_hourly_schedule_treats_zero_interval_as_hourly():
    assert _hourly_schedule(0).hour == _hourly_schedule(1).hour


def test_hourly_schedule_treats_negative_interval_as_hourly():
    assert _hourly_schedule(-1).hour == _hourly_schedule(1).hour


# --- build_schedule_entries() ---


def _default_config():
    return {
        "application_status_check_interval_hours": 4,
        "resubmit_times_utc": "09:00,21:00",
        "tournament_ingest_interval_hours": 1,
        "tournament_ingest_limit": 1000,
        "tournament_backfill_months": 3,
        "organizer_scan_interval_hours": 24,
        "organizer_scan_limit": 50,
        "organizer_scan_start_id": 2722,
    }


def _find_entry(entries, name):
    return next((e for e in entries if e[0] == name), None)


def test_build_schedule_entries_always_has_three_fixed_entries():
    entries = build_schedule_entries(_default_config())
    fixed = [e for e in entries if not e[0].startswith("resubmit-reminder-")]
    assert len(fixed) == 3


def test_build_schedule_entries_creates_status_check():
    entries = build_schedule_entries(_default_config())
    entry = _find_entry(entries, "check-application-status")
    assert entry is not None
    assert entry[1] == "app.tasks.status_tasks.check_application_status_task"
    assert isinstance(entry[2], crontab)


def test_build_schedule_entries_creates_tournament_ingestion():
    entries = build_schedule_entries(_default_config())
    entry = _find_entry(entries, "ingest-tournaments")
    assert entry is not None
    assert entry[1] == "app.tasks.tournament_tasks.ingest_tournaments_task"
    assert isinstance(entry[2], crontab)


def test_build_schedule_entries_creates_organizer_scan():
    entries = build_schedule_entries(_default_config())
    entry = _find_entry(entries, "scan-new-organizers")
    assert entry is not None
    assert entry[1] == "app.tasks.organizer_tasks.scan_new_organizers_task"
    assert isinstance(entry[2], timedelta)


def test_build_schedule_entries_status_check_uses_configured_interval():
    config = _default_config()
    config["application_status_check_interval_hours"] = 6
    entries = build_schedule_entries(config)
    entry = _find_entry(entries, "check-application-status")
    assert entry[2].hour == {0, 6, 12, 18}


def test_build_schedule_entries_tournament_ingestion_uses_configured_interval():
    config = _default_config()
    config["tournament_ingest_interval_hours"] = 3
    entries = build_schedule_entries(config)
    entry = _find_entry(entries, "ingest-tournaments")
    assert entry[2].hour == {0, 3, 6, 9, 12, 15, 18, 21}


def test_build_schedule_entries_organizer_scan_uses_configured_hours():
    config = _default_config()
    config["organizer_scan_interval_hours"] = 12
    entries = build_schedule_entries(config)
    entry = _find_entry(entries, "scan-new-organizers")
    assert entry[2] == timedelta(hours=12)


def test_build_schedule_entries_organizer_scan_treats_zero_as_one_hour():
    config = _default_config()
    config["organizer_scan_interval_hours"] = 0
    entries = build_schedule_entries(config)
    entry = _find_entry(entries, "scan-new-organizers")
    assert entry[2] == timedelta(hours=1)


def test_build_schedule_entries_creates_resubmit_entries():
    config = _default_config()
    config["resubmit_times_utc"] = "09:00,21:00"
    entries = build_schedule_entries(config)
    resubmit = [e for e in entries if e[0].startswith("resubmit-reminder-")]
    assert len(resubmit) == 2
    assert resubmit[0][0] == "resubmit-reminder-0900"
    assert resubmit[1][0] == "resubmit-reminder-2100"
    assert all(e[1] == "app.tasks.resubmit_tasks.resubmit_reminder_task" for e in resubmit)


def test_build_schedule_entries_resubmit_crontab_matches_time():
    config = _default_config()
    config["resubmit_times_utc"] = "14:30"
    entries = build_schedule_entries(config)
    entry = _find_entry(entries, "resubmit-reminder-1430")
    assert entry is not None
    assert entry[2].hour == {14}
    assert entry[2].minute == {30}


def test_build_schedule_entries_empty_resubmit_times():
    config = _default_config()
    config["resubmit_times_utc"] = ""
    entries = build_schedule_entries(config)
    resubmit = [e for e in entries if e[0].startswith("resubmit-reminder-")]
    assert len(resubmit) == 0


def test_build_schedule_entries_single_resubmit_time():
    config = _default_config()
    config["resubmit_times_utc"] = "10:00"
    entries = build_schedule_entries(config)
    resubmit = [e for e in entries if e[0].startswith("resubmit-reminder-")]
    assert len(resubmit) == 1
    assert resubmit[0][0] == "resubmit-reminder-1000"


# --- build_beat_schedule() (mocked Redis) ---


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_saves_entries_to_redis(mock_get_redis, MockEntry):
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = set()
    mock_get_redis.return_value = mock_redis

    mock_entry_instance = MagicMock()
    MockEntry.return_value = mock_entry_instance

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    assert MockEntry.call_count == 5  # 3 fixed + 2 resubmit
    assert mock_entry_instance.save.call_count == 5


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_tracks_entry_names_in_redis(mock_get_redis, MockEntry):
    from app.celery_app import MANAGED_ENTRIES_REDIS_KEY, build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = set()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_get_redis.return_value = mock_redis
    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    mock_pipe.sadd.assert_called_once()
    call_args = mock_pipe.sadd.call_args
    assert call_args[0][0] == MANAGED_ENTRIES_REDIS_KEY
    stored_names = set(call_args[0][1:])
    assert "check-application-status" in stored_names
    assert "ingest-tournaments" in stored_names
    assert "scan-new-organizers" in stored_names
    assert "resubmit-reminder-0900" in stored_names
    assert "resubmit-reminder-2100" in stored_names


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_deletes_stale_entries(mock_get_redis, MockEntry):
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = {"resubmit-reminder-0800", "old-entry"}
    mock_redis.pipeline.return_value = MagicMock()
    mock_get_redis.return_value = mock_redis

    mock_old_entry = MagicMock()
    MockEntry.from_key.return_value = mock_old_entry
    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    assert MockEntry.from_key.call_count == 2
    assert mock_old_entry.delete.call_count == 2


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_deletes_legacy_resubmit_application_entries(mock_get_redis, MockEntry):
    """Phase 54 (#152) migration: real production Redis holds pre-existing
    resubmit-application-* entries from before the reminder rename; these must
    still get swept up as stale even though the new schedule only produces
    resubmit-reminder-* names."""
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = {"resubmit-application-0900", "resubmit-application-2100"}
    mock_redis.pipeline.return_value = MagicMock()
    mock_get_redis.return_value = mock_redis

    mock_old_entry = MagicMock()
    MockEntry.from_key.return_value = mock_old_entry
    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    deleted_keys = [call.args[0] for call in MockEntry.from_key.call_args_list]
    assert "redbeat:resubmit-application-0900" in deleted_keys
    assert "redbeat:resubmit-application-2100" in deleted_keys
    assert mock_old_entry.delete.call_count == 2


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_tolerates_missing_old_entries(mock_get_redis, MockEntry):
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = {"ghost-entry"}
    mock_get_redis.return_value = mock_redis

    MockEntry.from_key.side_effect = KeyError("not found")
    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    assert MockEntry.return_value.save.call_count == 5


# --- Phase 44 (#119): atomic build_beat_schedule ---


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_creates_before_deleting_stale(mock_get_redis, MockEntry):
    """New entries must be saved BEFORE stale old entries are deleted (no gap)."""
    from app.celery_app import build_beat_schedule

    call_order = []

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = {"stale-entry"}
    mock_get_redis.return_value = mock_redis

    mock_old_entry = MagicMock()
    mock_old_entry.delete.side_effect = lambda: call_order.append("delete:stale-entry")
    MockEntry.from_key.return_value = mock_old_entry

    mock_new_entry = MagicMock()
    mock_new_entry.save.side_effect = lambda: call_order.append("save")
    MockEntry.return_value = mock_new_entry

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    first_save = call_order.index("save")
    first_delete = call_order.index("delete:stale-entry")
    assert first_save < first_delete, "New entries must be saved before stale entries are deleted"


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_only_deletes_stale_entries(mock_get_redis, MockEntry):
    """Entries that exist in both old and new sets should NOT be deleted."""
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = {
        "check-application-status",  # exists in new set
        "stale-entry",               # does NOT exist in new set
    }
    mock_get_redis.return_value = mock_redis

    mock_old_entry = MagicMock()
    MockEntry.from_key.return_value = mock_old_entry
    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    from_key_calls = [call.args[0] for call in MockEntry.from_key.call_args_list]
    assert "redbeat:stale-entry" in from_key_calls
    assert "redbeat:check-application-status" not in from_key_calls


@patch("app.celery_app.RedBeatSchedulerEntry")
@patch("app.celery_app.get_redis")
def test_build_beat_schedule_updates_tracking_set_atomically(mock_get_redis, MockEntry):
    """The tracking set update should use a Redis pipeline for atomicity."""
    from app.celery_app import build_beat_schedule

    mock_redis = MagicMock()
    mock_redis.smembers.return_value = set()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_get_redis.return_value = mock_redis

    MockEntry.return_value = MagicMock()

    config = _default_config()
    build_beat_schedule(MagicMock(), config)

    mock_redis.pipeline.assert_called_once()
    mock_pipe.delete.assert_called_once()
    mock_pipe.sadd.assert_called_once()
    mock_pipe.execute.assert_called_once()
