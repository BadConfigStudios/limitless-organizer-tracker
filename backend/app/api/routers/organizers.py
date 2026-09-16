from datetime import date, datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.analytics.buckets import bucket_dates
from app.analytics.frontier import build_frontier_regression
from app.api.schemas import (
    ActivityBucketOut,
    BackfillResultOut,
    FittedLineEndpointOut,
    HighestOrganizerIdOut,
    OnboardingDeltaOut,
    OrganizerProfileOut,
    RecentlyOnboardedOut,
    WaitEstimateOut,
    WaitEstimatePointOut,
)
from app.config import settings
from app.db.models import Organizer, OrganizerActivity
from app.db.session import get_db
from app.limitless_client.ingestion import sync_organizer_first_tournament_dates
from app.scraper.organizer_profile import earliest_tournament_date, parse_organizer_profile

MAX_CHART_POINTS = 200

router = APIRouter(prefix="/api", tags=["organizers"], dependencies=[Depends(require_api_key)])


@router.get("/games", response_model=list[str])
def get_games(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(select(OrganizerActivity.game).distinct().order_by(OrganizerActivity.game)))


@router.get("/organizers/activity", response_model=list[ActivityBucketOut])
def get_organizer_activity(
    interval: Literal["week", "month"] = Query("week"),
    game: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ActivityBucketOut]:
    stmt = select(OrganizerActivity.first_tournament_date)
    if game is not None:
        stmt = stmt.where(OrganizerActivity.game == game)

    dates = db.scalars(stmt).all()
    buckets = bucket_dates(dates, interval)
    return [ActivityBucketOut(period=period, count=count) for period, count in buckets]


def _predict_date(result, organizer_id: int) -> date:
    projected_ordinal = round(result.predict(float(organizer_id)))
    projected_ordinal = max(date.min.toordinal(), min(date.max.toordinal(), projected_ordinal))
    return date.fromordinal(projected_ordinal)


@router.get("/organizers/wait-estimate", response_model=WaitEstimateOut)
def get_wait_estimate(
    organizer_id: int | None = Query(None),
    days: int | None = Query(None),
    db: Session = Depends(get_db),
) -> WaitEstimateOut:
    points, frontier_points, result = build_frontier_regression(db, days=days)
    if points is None:
        raise HTTPException(status_code=404, detail="not enough activity data to estimate")

    frontier_ids = {p[0] for p in frontier_points}

    projected_date = _predict_date(result, organizer_id) if organizer_id is not None else None

    all_point_outs = [
        WaitEstimatePointOut(
            organizer_id=int(oid),
            first_tournament_date=date.fromordinal(int(ordinal)),
            is_frontier=oid in frontier_ids,
        )
        for oid, ordinal in points
    ]
    sample_size = len(all_point_outs)

    if len(all_point_outs) > MAX_CHART_POINTS:
        frontier = [p for p in all_point_outs if p.is_frontier]
        non_frontier = [p for p in all_point_outs if not p.is_frontier]
        budget = MAX_CHART_POINTS - len(frontier)
        if budget > 0 and non_frontier:
            step = max(1, len(non_frontier) // budget)
            sampled = non_frontier[::step][:budget]
            all_point_outs = sorted(frontier + sampled, key=lambda p: p.organizer_id)
        else:
            all_point_outs = frontier

    point_ids = [oid for oid, _ in points]
    target_ids = [float(organizer_id)] if organizer_id is not None else []
    all_ids = point_ids + target_ids
    min_id = int(min(all_ids))
    max_id = int(max(all_ids))
    fitted_line = [
        FittedLineEndpointOut(organizer_id=min_id, projected_date=_predict_date(result, min_id)),
        FittedLineEndpointOut(organizer_id=max_id, projected_date=_predict_date(result, max_id)),
    ]

    return WaitEstimateOut(
        organizer_id=organizer_id,
        slope=result.slope,
        r_squared=result.r_squared,
        projected_active_date=projected_date,
        sample_size=sample_size,
        frontier_size=len(frontier_points),
        total_points=sample_size,
        fitted_line=fitted_line,
        points=all_point_outs,
    )


@router.post("/organizers/backfill-first-tournament-date", response_model=BackfillResultOut)
def backfill_first_tournament_date(db: Session = Depends(get_db)) -> BackfillResultOut:
    """Back-populate Organizer.first_tournament_date from OrganizerActivity for any row where it is NULL."""
    null_ids = set(db.scalars(
        select(Organizer.organizer_id).where(Organizer.first_tournament_date.is_(None))
    ).all())

    if not null_ids:
        return BackfillResultOut(updated=0)

    sync_organizer_first_tournament_dates(db, null_ids)

    updated = db.scalar(
        select(func.count()).select_from(Organizer)
        .where(Organizer.organizer_id.in_(null_ids), Organizer.first_tournament_date.isnot(None))
    )
    db.commit()
    return BackfillResultOut(updated=updated or 0)


@router.get("/organizers/onboarding-history", response_model=list[ActivityBucketOut])
def get_onboarding_history(
    interval: Literal["day", "week"] = Query("day"),
    db: Session = Depends(get_db),
) -> list[ActivityBucketOut]:
    dates = db.scalars(
        select(Organizer.onboarded_at).where(Organizer.onboarded_at.isnot(None))
    ).all()
    buckets = bucket_dates(list(dates), interval)
    return [ActivityBucketOut(period=period, count=count) for period, count in buckets]


@router.get("/organizers/onboarding-delta", response_model=OnboardingDeltaOut)
def get_onboarding_delta(
    db: Session = Depends(get_db),
) -> OnboardingDeltaOut:
    rows = db.execute(
        select(Organizer.onboarded_at, Organizer.first_tournament_date)
        .where(
            Organizer.onboarded_at.isnot(None),
            Organizer.first_tournament_date.isnot(None),
            Organizer.first_tournament_date >= Organizer.onboarded_at,
        )
    ).all()

    if not rows:
        return OnboardingDeltaOut(avg_days=0.0, median_days=0.0, count=0)

    deltas = sorted((ftd - oba).days for oba, ftd in rows)
    count = len(deltas)
    avg_days = sum(deltas) / count

    if count % 2 == 1:
        median_days = float(deltas[count // 2])
    else:
        mid = count // 2
        median_days = (deltas[mid - 1] + deltas[mid]) / 2.0

    return OnboardingDeltaOut(avg_days=avg_days, median_days=median_days, count=count)


@router.get("/organizers/recently-onboarded", response_model=list[RecentlyOnboardedOut])
def get_recently_onboarded(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[RecentlyOnboardedOut]:
    rows = db.execute(
        select(Organizer)
        .where(Organizer.detected_at.isnot(None))
        .order_by(Organizer.detected_at.desc())
        .limit(limit)
    ).scalars().all()
    return [RecentlyOnboardedOut.model_validate(r) for r in rows]


@router.get("/organizers/highest-id", response_model=HighestOrganizerIdOut)
def get_highest_organizer_id(db: Session = Depends(get_db)) -> HighestOrganizerIdOut:
    highest = db.scalar(select(func.max(Organizer.organizer_id)))
    if highest is None:
        highest = db.scalar(select(func.max(OrganizerActivity.organizer_id)))
    if highest is None:
        raise HTTPException(status_code=404, detail="no organizer data available")
    return HighestOrganizerIdOut(organizer_id=highest)


def _estimate_onboard_date(db: Session, organizer_id: int) -> date | None:
    _, _, result = build_frontier_regression(db)
    if result is None:
        return None
    return _predict_date(result, organizer_id)


@router.get("/organizers/{organizer_id}/scrape", response_model=OrganizerProfileOut)
def scrape_organizer_profile(
    organizer_id: int = Path(ge=1),
    db: Session = Depends(get_db),
) -> OrganizerProfileOut:
    url = f"{settings.limitless_base_url}/organizer/{organizer_id}"
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="failed to reach Limitless")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="organizer not found on Limitless")
    if not resp.is_success:
        raise HTTPException(status_code=502, detail=f"Limitless returned {resp.status_code}")

    profile = parse_organizer_profile(resp.text, organizer_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="organizer profile could not be parsed")

    result = OrganizerProfileOut.model_validate(profile)

    scraped_first_date = earliest_tournament_date(profile)

    org = db.get(Organizer, organizer_id)
    if org is None:
        org = db.merge(Organizer(organizer_id=organizer_id, detected_at=datetime.now(timezone.utc)))

    if scraped_first_date is not None:
        if org.first_tournament_date is None or scraped_first_date < org.first_tournament_date:
            org.first_tournament_date = scraped_first_date

    db.commit()
    db.refresh(org)

    result.onboarded_at = org.onboarded_at
    result.first_tournament_date = org.first_tournament_date
    result.detected_at = org.detected_at

    if org.onboarded_at is None:
        result.estimated_onboard_date = _estimate_onboard_date(db, organizer_id)

    return result
