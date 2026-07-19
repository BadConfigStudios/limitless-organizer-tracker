# Developer Guide

This project is built incrementally, one phase per pull request, against the
build order tracked in [Requirements](requirements.md). See
[Getting Started](getting-started.md) for local setup first.

## Contribution workflow

Each phase corresponds to a GitHub issue (see the Build Order table in
[Requirements](requirements.md)) and follows the same cycle:

1. **Branch off `main`**: `git checkout -b feature/<phase-slug>`. Branch
   before any code or test changes — never commit phase work to `main`
   directly.
2. **Write tests first (RED)**: acceptance tests (in `tests/acceptance/`,
   with Given/When/Then docstrings referencing the FR IDs they cover), then
   unit tests, then integration tests. Confirm they fail before
   implementing.
3. **Implement until GREEN**: write the minimum code to pass the new tests.
4. **Run the full suite**: `pytest` (backend) and `npm run test -- --run`
   (frontend). Run `ruff check app tests` / `npm run lint`.
5. **Update docs**: [Requirements](requirements.md) status column for any
   FR/NFR the phase completes, plus any other affected docs.
6. **Update `CHANGELOG.md`**: add an entry under `[Unreleased]` describing
   what was added/changed, referencing the FR/NFR IDs.
7. **Commit** tests, implementation, and docs together.
8. **Push and open a PR**: `git push -u origin feature/<phase-slug>`, then
   `gh pr create` referencing `Closes #<issue>`.
9. **Review**: `/code-review` and `/security-review` are run on the PR
   before merge. Address any findings with follow-up commits on the same
   branch.
10. **Manual verification**: bring up the stack (`docker compose up --build`)
    and walk through the new/changed behavior before merge.
11. **Merge**: only after review passes, manual verification is complete,
    and the owner approves.

Full detail (commit message format, technical-decision sign-off) lives in
[`CONTRIBUTING.md`](https://github.com/badconfigstudios/limitless-organizer-tracker/blob/main/CONTRIBUTING.md)
at the repo root.

## Test layout

- `tests/unit/` — pure logic (parsing, schemas, models, aggregation), no
  I/O.
- `tests/integration/` — FastAPI `TestClient`, SQLite-backed DB
  round-trips, and external APIs mocked with `respx`.
- `tests/acceptance/` — Given/When/Then style tests that trace back to the
  FR IDs in [Requirements](requirements.md).
- `tests/fixtures/` — sample HTML/JSON used by unit and integration tests.

All three layers follow RED → GREEN → REFACTOR. Not every change needs all
three, but skipping integration tests for a change that crosses a boundary
(API ↔ DB, scraper ↔ live site) is a gap, not a shortcut.

## Database migrations

Schema changes go through Alembic (`backend/alembic/`). After changing a
SQLAlchemy model:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Commit the generated migration alongside the model change.

## Scraper selectors

The Playwright-based scraper (login, status check, resubmit) targets
`play.limitlesstcg.com` CSS selectors defined in `app/scraper/selectors.py`.
These were validated against the live site during development but may
drift if Limitless updates their front end — see
[Live scraper tests](getting-started.md#live-scraper-tests). The organizer
onboarding scanner (`scan_new_organizers_task`) uses plain `httpx` against
public profile pages — no selectors, no login required.

## Technical decisions

Any non-trivial technical decision — new dependency, choice between
libraries or patterns, file/module structure, auth/session design, API
design, CI/CD or GitHub repo configuration — must be presented to the owner
with alternatives and tradeoffs **before** it is implemented. Once approved,
it's recorded in
[`DECISIONS.md`](https://github.com/badconfigstudios/limitless-organizer-tracker/blob/main/DECISIONS.md).

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR:
backend lint (`ruff`) + tests (`pytest --cov=app`, including Playwright
install), frontend lint + tests, a docs build (`mkdocs build --strict`),
and `docker-build` on pushes to `main` only.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) format:
`type(scope): short description`. Every commit must include:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```
