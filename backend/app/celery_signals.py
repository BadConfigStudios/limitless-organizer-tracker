"""Celery task lifecycle signal handlers for automatic event logging.

Wired via connect_signals() called from celery_app.py. Handlers are
exception-safe — a logging failure never crashes a running task.
"""

import logging
import time

from celery.signals import beat_init, task_failure, task_postrun, task_prerun

from app.db.session import SessionLocal
from app.events import log_event

logger = logging.getLogger(__name__)

_MAX_TRACKED_TASKS = 1000
_task_start_times: dict[str, float] = {}


def on_task_prerun(sender=None, task_id=None, **kwargs):
    try:
        if len(_task_start_times) >= _MAX_TRACKED_TASKS:
            _task_start_times.clear()
        _task_start_times[task_id] = time.monotonic()
        task_name = getattr(sender, "__name__", str(sender))
        session = SessionLocal()
        try:
            log_event(
                session=session,
                event_type="task.started",
                source="celery",
                message=f"{task_name} started",
                correlation_id=task_id,
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.debug("Failed to log task_prerun", exc_info=True)


def on_task_postrun(sender=None, task_id=None, retval=None, **kwargs):
    try:
        start = _task_start_times.pop(task_id, None)
        duration_ms = (time.monotonic() - start) * 1000 if start is not None else None
        task_name = getattr(sender, "__name__", str(sender))
        session = SessionLocal()
        try:
            log_event(
                session=session,
                event_type="task.completed",
                source="celery",
                message=f"{task_name} completed",
                correlation_id=task_id,
                details={
                    "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
                    "result": str(retval)[:500],
                },
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.debug("Failed to log task_postrun", exc_info=True)


def on_task_failure(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    try:
        start = _task_start_times.pop(task_id, None)
        duration_ms = (time.monotonic() - start) * 1000 if start is not None else None
        task_name = getattr(sender, "__name__", str(sender))
        session = SessionLocal()
        try:
            log_event(
                session=session,
                event_type="task.failed",
                source="celery",
                message=f"{task_name} failed",
                severity="ERROR",
                correlation_id=task_id,
                details={
                    "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
                    "error": str(exception)[:1000],
                },
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.debug("Failed to log task_failure", exc_info=True)


def on_beat_init(sender=None, **kwargs):
    from app.celery_app import build_beat_schedule
    from app.config import settings
    from app.config_db import EDITABLE_CONFIG_KEYS, get_effective_config

    config = None
    try:
        session = SessionLocal()
        try:
            config = get_effective_config(session)
        finally:
            session.close()
    except Exception:
        logger.warning("DB unavailable at beat startup, using env-var defaults", exc_info=True)

    if config is None:
        config = {key: getattr(settings, key) for key in EDITABLE_CONFIG_KEYS}

    try:
        build_beat_schedule(sender.app, config)
    except Exception:
        logger.error("Failed to build beat schedule on startup", exc_info=True)
        try:
            session = SessionLocal()
            try:
                log_event(
                    session=session,
                    event_type="beat.schedule_rebuild_failed",
                    source="celery_signals",
                    message="Beat schedule rebuild failed on startup — schedule may be stale",
                    severity="ERROR",
                )
                session.commit()
            finally:
                session.close()
        except Exception:
            logger.debug("Failed to log beat.schedule_rebuild_failed event", exc_info=True)


def connect_signals():
    task_prerun.connect(on_task_prerun)
    task_postrun.connect(on_task_postrun)
    task_failure.connect(on_task_failure)
    beat_init.connect(on_beat_init)
