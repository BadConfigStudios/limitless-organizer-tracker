import logging
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from redbeat import RedBeatSchedulerEntry
from redbeat.schedulers import get_redis

from app.celery_signals import connect_signals
from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "limitless_organizer_tracker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.status_tasks",
        "app.tasks.resubmit_tasks",
        "app.tasks.tournament_tasks",
        "app.tasks.organizer_tasks",
        "app.tasks.backfill_tasks",
    ],
)

celery_app.conf.redbeat_redis_url = settings.celery_broker_url
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"

MANAGED_ENTRIES_REDIS_KEY = "lot:managed-beat-entries"


def parse_resubmit_times(value: str) -> list[tuple[int, int]]:
    """Parse a comma-separated "HH:MM,HH:MM" string into (hour, minute) tuples.

    Blank entries (including an empty `value`) are skipped, so an empty
    string yields no scheduled resubmit times rather than raising.
    """
    times = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        hour, minute = part.split(":")
        times.append((int(hour), int(minute)))
    return times


def _hourly_schedule(interval_hours: int) -> crontab:
    """Build an every-N-hours crontab, treating a non-positive interval as hourly.

    `crontab(hour="*/0")` raises ValueError, so a misconfigured interval of 0
    (or less) falls back to running every hour instead of crashing on import.
    """
    hours = interval_hours if interval_hours > 0 else 1
    return crontab(minute=0, hour=f"*/{hours}")


def build_schedule_entries(config: dict) -> list[tuple[str, str, crontab | timedelta]]:
    """Build (name, task, schedule) tuples from effective config."""
    scan_hours = config["organizer_scan_interval_hours"]
    entries: list[tuple[str, str, crontab | timedelta]] = [
        (
            "check-application-status",
            "app.tasks.status_tasks.check_application_status_task",
            _hourly_schedule(config["application_status_check_interval_hours"]),
        ),
        (
            "ingest-tournaments",
            "app.tasks.tournament_tasks.ingest_tournaments_task",
            _hourly_schedule(config["tournament_ingest_interval_hours"]),
        ),
        (
            "scan-new-organizers",
            "app.tasks.organizer_tasks.scan_new_organizers_task",
            timedelta(hours=max(scan_hours, 1)),
        ),
    ]
    for hour, minute in parse_resubmit_times(config["resubmit_times_utc"]):
        entries.append((
            f"resubmit-reminder-{hour:02d}{minute:02d}",
            "app.tasks.resubmit_tasks.resubmit_reminder_task",
            crontab(hour=hour, minute=minute),
        ))
    return entries


def build_beat_schedule(app, config: dict) -> None:
    """Write RedBeatSchedulerEntry objects to Redis from the given config.

    Creates new entries before deleting stale ones so the beat scheduler
    never sees an empty schedule during the rebuild window.
    """
    entries = build_schedule_entries(config)
    redis_client = get_redis(app)

    old_names = {
        n.decode() if isinstance(n, bytes) else n
        for n in redis_client.smembers(MANAGED_ENTRIES_REDIS_KEY)
    }

    new_names = []
    for name, task, schedule in entries:
        RedBeatSchedulerEntry(name, task, schedule, app=app).save()
        new_names.append(name)

    new_names_set = set(new_names)
    for name in old_names - new_names_set:
        try:
            old_entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", app=app)
            old_entry.delete()
        except Exception:
            logger.debug("Failed to delete stale beat entry %s", name, exc_info=True)

    pipe = redis_client.pipeline()
    pipe.delete(MANAGED_ENTRIES_REDIS_KEY)
    if new_names:
        pipe.sadd(MANAGED_ENTRIES_REDIS_KEY, *new_names)
    pipe.execute()

    logger.info("Beat schedule rebuilt: %d entries", len(new_names))


connect_signals()
