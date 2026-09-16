from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.regression import fit_linear_regression
from app.db.models import OrganizerActivity

TOP_N_ORGANIZERS = 1000


def build_frontier_regression(session: Session, days: int | None = None):
    stmt = (
        select(
            OrganizerActivity.organizer_id,
            func.min(OrganizerActivity.first_tournament_date).label("first_tournament_date"),
        )
        .group_by(OrganizerActivity.organizer_id)
    )
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.having(func.min(OrganizerActivity.first_tournament_date) >= cutoff)

    rows = session.execute(
        stmt.order_by(OrganizerActivity.organizer_id.desc()).limit(TOP_N_ORGANIZERS)
    ).all()
    if len(rows) < 2:
        return None, None, None

    points = [(float(oid), float(first_date.date().toordinal())) for oid, first_date in reversed(rows)]
    frontier_points = compute_frontier(points)
    regression_points = frontier_points if len(frontier_points) >= 2 else points
    result = fit_linear_regression(regression_points)
    return points, frontier_points, result


def compute_frontier(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the Pareto-optimal (lower-envelope) subset of (organizer_id, date_ordinal) points.

    A point is on the frontier iff no other point with an equal-or-higher organizer_id
    has a strictly earlier date — i.e., it represents the fastest observed
    onboarding-to-first-event lag for its ID range.

    Input may be in any order. Output is sorted ascending by organizer_id.
    """
    if not points:
        return []

    frontier: list[tuple[float, float]] = []
    running_min = float("inf")

    for organizer_id, date_ordinal in sorted(points, key=lambda p: p[0], reverse=True):
        if date_ordinal <= running_min:
            frontier.append((organizer_id, date_ordinal))
            running_min = date_ordinal

    frontier.reverse()
    return frontier
