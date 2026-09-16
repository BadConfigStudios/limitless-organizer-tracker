from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import require_api_key, require_session
from app.api.pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate
from app.api.schemas import Page, ResubmissionEventOut, StatusCheckOut
from app.db.models import ApplicationStatusCheck, ResubmissionEvent
from app.db.session import get_db
from app.tasks.status_tasks import check_application_status_task

router = APIRouter(
    prefix="/api", tags=["status"], dependencies=[Depends(require_api_key), Depends(require_session)]
)

STATUS_CHECK_TIMEOUT_SECONDS = 60


@router.post("/status-check", response_model=StatusCheckOut)
def post_status_check(db: Session = Depends(get_db)) -> ApplicationStatusCheck:
    """Dispatch an application-status check to the Celery worker and return the result (FR14)."""
    try:
        check_id = check_application_status_task.delay().get(
            timeout=STATUS_CHECK_TIMEOUT_SECONDS
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Status check task failed or timed out")
    check = db.get(ApplicationStatusCheck, check_id)
    if check is None:
        raise HTTPException(status_code=500, detail="Status check result not found")
    return check


@router.get("/status-history", response_model=Page[StatusCheckOut])
def get_status_history(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[StatusCheckOut]:
    items, total = paginate(
        db,
        ApplicationStatusCheck,
        (ApplicationStatusCheck.checked_at.desc(), ApplicationStatusCheck.id.desc()),
        limit,
        offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/resubmissions", response_model=Page[ResubmissionEventOut])
def get_resubmissions(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[ResubmissionEventOut]:
    items, total = paginate(
        db,
        ResubmissionEvent,
        (ResubmissionEvent.submitted_at.desc(), ResubmissionEvent.id.desc()),
        limit,
        offset,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)
