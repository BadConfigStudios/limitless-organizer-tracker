from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_api_key, require_session
from app.api.schemas import ResubmissionEventOut, TaskResultOut
from app.db.models import ResubmissionEvent
from app.db.session import get_db
from app.tasks.backfill_tasks import (
    backfill_organizers_from_tournaments_task,
    historical_organizer_scan_task,
    verify_frontier_regression_task,
)
from app.tasks.organizer_tasks import audit_organizer_scan_task
from app.tasks.resubmit_tasks import resubmit_application_task
from app.tasks.tournament_tasks import audit_backfill_task, ingest_tournaments_task

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_api_key), Depends(require_session)],
)

TASK_TIMEOUT_SECONDS = 120


@router.post("/ingest-tournaments", response_model=TaskResultOut)
def trigger_ingest_tournaments() -> dict:
    """Trigger a tournament ingestion run on the Celery worker.

    Fetches tournament data from the Limitless API across all games,
    paginating back through the configured backfill window. Upserts
    tournaments and organizer-activity records. Returns the count of
    tournaments processed.
    """
    try:
        result = ingest_tournaments_task.delay()
        count = result.get(timeout=TASK_TIMEOUT_SECONDS)
    except Exception:
        raise HTTPException(status_code=500, detail="Tournament ingestion task failed or timed out")
    return TaskResultOut(
        task_id=result.id,
        status="completed",
        result=f"Ingested {count} tournaments",
    )


@router.post("/full-backfill", response_model=TaskResultOut)
def trigger_full_backfill() -> dict:
    """Trigger a full historical tournament backfill on the Celery worker.

    Audits the Limitless API to discover all pages, then dispatches one
    task per page. Returns immediately — monitor progress via the event log.
    """
    result = audit_backfill_task.delay()
    return TaskResultOut(
        task_id=result.id,
        status="started",
        result="Backfill audit started — page tasks will be queued after discovery. Monitor progress in the event log.",
    )


@router.post("/scan-organizers", response_model=TaskResultOut)
def trigger_scan_organizers() -> dict:
    """Trigger an organizer scan on the Celery worker.

    Audits organizer IDs from the current watermark, then dispatches
    per-organizer scan tasks. Returns immediately — monitor progress
    via the event log.
    """
    result = audit_organizer_scan_task.delay()
    return TaskResultOut(
        task_id=result.id,
        status="started",
        result="Organizer scan audit started — individual scan tasks will be queued. Monitor progress in the event log.",
    )


@router.post("/backfill-organizers", response_model=TaskResultOut)
def trigger_backfill_organizers() -> dict:
    """Trigger a one-time backfill of Organizer rows from tournament data.

    Creates Organizer rows for all organizer_ids in the tournaments table
    that lack one. Returns immediately — monitor progress via the event log.
    """
    result = backfill_organizers_from_tournaments_task.delay()
    return TaskResultOut(
        task_id=result.id,
        status="started",
        result="Organizer backfill started — monitor progress in the event log.",
    )


@router.post("/historical-organizer-scan", response_model=TaskResultOut)
def trigger_historical_organizer_scan() -> dict:
    """Trigger a historical organizer ID scan (1 through watermark).

    Probes each missing organizer ID via HTTP and dispatches
    scan_single_organizer_task for each 200. Continues past 404/500.
    Returns immediately — monitor progress via the event log.
    """
    result = historical_organizer_scan_task.delay()
    return TaskResultOut(
        task_id=result.id,
        status="started",
        result="Historical organizer scan started — monitor progress in the event log.",
    )


@router.post("/verify-frontier-regression", response_model=TaskResultOut)
def trigger_verify_frontier_regression() -> dict:
    """Trigger frontier regression verification on the Celery worker.

    Counts Organizer rows, runs the frontier regression, and logs
    slope/R²/frontier_size/sample_size as an event.
    Returns immediately — monitor progress via the event log.
    """
    result = verify_frontier_regression_task.delay()
    return TaskResultOut(
        task_id=result.id,
        status="started",
        result="Frontier regression verification started — monitor progress in the event log.",
    )


@router.post("/resubmit-application", response_model=ResubmissionEventOut)
def trigger_resubmit_application(db: Session = Depends(get_db)) -> ResubmissionEvent:
    """Trigger an application resubmission on the Celery worker.

    Logs into play.limitlesstcg.com via Playwright, resubmits the
    organization application, posts a Discord notification, and records
    the outcome. Returns the full resubmission event record.
    """
    try:
        result = resubmit_application_task.delay()
        event_id = result.get(timeout=TASK_TIMEOUT_SECONDS)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Resubmission task failed or timed out"
        )
    event = db.get(ResubmissionEvent, event_id)
    if event is None:
        raise HTTPException(status_code=500, detail="Resubmission result not found")
    return event
