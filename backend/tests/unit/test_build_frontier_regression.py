"""Unit tests for build_frontier_regression() (Phase 49, #139).

Tests the extracted frontier regression builder that queries OrganizerActivity
and returns points, frontier_points, and a RegressionResult.
"""

from datetime import datetime, timedelta, timezone

from app.analytics.frontier import build_frontier_regression
from app.db.models import OrganizerActivity


def _add_activity(session, organizer_id, first_dt, game="PTCG"):
    session.add(OrganizerActivity(
        organizer_id=organizer_id, game=game,
        first_tournament_date=first_dt, first_tournament_id="t-dummy",
        last_seen_date=first_dt, updated_at=datetime.now(timezone.utc),
    ))
    session.flush()


def test_returns_none_when_no_data(db_session):
    """Returns (None, None, None) when OrganizerActivity is empty."""
    result = build_frontier_regression(db_session)
    assert result == (None, None, None)


def test_returns_none_when_single_organizer(db_session):
    """Returns (None, None, None) with fewer than 2 organizers."""
    _add_activity(db_session, 100, datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.commit()

    result = build_frontier_regression(db_session)
    assert result == (None, None, None)


def test_returns_points_frontier_regression_with_sufficient_data(db_session):
    """Returns (points, frontier_points, result) when >= 2 organizers exist."""
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 200, datetime(2025, 6, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 300, datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.commit()

    points, frontier_points, result = build_frontier_regression(db_session)

    assert points is not None
    assert len(points) == 3
    assert frontier_points is not None
    assert len(frontier_points) >= 1
    assert result is not None
    assert hasattr(result, "slope")
    assert hasattr(result, "r_squared")


def test_uses_min_first_tournament_date_per_organizer(db_session):
    """When an organizer has multiple games, uses MIN(first_tournament_date)."""
    _add_activity(db_session, 100, datetime(2025, 6, 1, tzinfo=timezone.utc), game="PTCG")
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc), game="POKEMON")
    _add_activity(db_session, 200, datetime(2025, 12, 1, tzinfo=timezone.utc))
    db_session.commit()

    points, _, _ = build_frontier_regression(db_session)

    point_map = {int(oid): ordinal for oid, ordinal in points}
    assert point_map[100] == float(datetime(2025, 1, 1).date().toordinal())


def test_points_sorted_ascending_by_organizer_id(db_session):
    """Points list is sorted ascending by organizer_id."""
    _add_activity(db_session, 300, datetime(2026, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 200, datetime(2025, 6, 1, tzinfo=timezone.utc))
    db_session.commit()

    points, _, _ = build_frontier_regression(db_session)

    ids = [int(oid) for oid, _ in points]
    assert ids == sorted(ids)


def test_regression_result_has_positive_slope(db_session):
    """With chronologically increasing dates and IDs, slope should be positive."""
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 200, datetime(2025, 6, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 300, datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.commit()

    _, _, result = build_frontier_regression(db_session)

    assert result.slope > 0


def test_days_filter_excludes_points_outside_window(db_session, monkeypatch):
    """When days is set, points outside the window are excluded BEFORE frontier/regression,
    not just from the final result — a stale organizer with a very early date must not
    pull the regression toward it even indirectly."""
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "app.analytics.frontier.datetime",
        type("_FixedDatetime", (), {"now": staticmethod(lambda tz=None: now)}),
    )
    _add_activity(db_session, 100, now - timedelta(days=200))  # outside 90-day window
    _add_activity(db_session, 200, now - timedelta(days=10))
    _add_activity(db_session, 300, now - timedelta(days=5))
    db_session.commit()

    points, frontier_points, result = build_frontier_regression(db_session, days=90)

    ids = {int(oid) for oid, _ in points}
    assert ids == {200, 300}
    assert 100 not in ids


def test_days_none_behaves_exactly_as_before(db_session):
    """days=None (the default) must not change existing all-time behavior."""
    _add_activity(db_session, 100, datetime(2025, 1, 1, tzinfo=timezone.utc))
    _add_activity(db_session, 200, datetime(2025, 6, 1, tzinfo=timezone.utc))
    db_session.commit()

    with_none = build_frontier_regression(db_session, days=None)
    without_arg = build_frontier_regression(db_session)

    assert [p for p in with_none[0]] == [p for p in without_arg[0]]
