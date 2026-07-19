# Getting Started

## Prerequisites

- Python 3.12+
- Docker + Docker Compose (for Postgres, Redis, and the full stack)
- Node.js 20+ (for the frontend)

## Clone and configure

```bash
git clone https://github.com/badconfigstudios/limitless-organizer-tracker.git
cd limitless-organizer-tracker
cp .env.example .env
```

Fill in real values in `.env` — at minimum `LIMITLESS_USERNAME`,
`LIMITLESS_PASSWORD`, and `LIMITLESS_APPLICATION_ID` if you want the
scraper to do anything useful locally. `.env` is gitignored; never commit
real credentials. See [Configuration](configuration.md) for the full
variable reference.

## Run the full stack

```bash
docker compose up
```

This brings up six services: `postgres`, `redis`, `backend` (FastAPI on
`:8000`, auto-reload), `celery-worker`, `celery-beat`, and `frontend` (Vite
dev server on `:5173`). Check the backend is healthy:

```bash
curl localhost:8000/healthz
```

Dashboard: [http://localhost:5173](http://localhost:5173). Run the backend
test suite inside Docker:

```bash
docker compose run --rm backend pytest
```

## Backend: local development (without Docker)

For fast TDD against the backend alone (Postgres/Redis still run via
Docker Compose):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite (fast, no live network calls — `@pytest.mark.live`
tests are excluded by default via `addopts = "-m 'not live'"` in
`pyproject.toml`):

```bash
pytest
```

Run lint:

```bash
ruff check app tests
```

## Frontend: local development (without Docker)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `VITE_API_PROXY_TARGET`
(default `http://localhost:8000`), so run the backend separately (either
via `docker compose up backend postgres redis celery-worker celery-beat`,
or the local-venv flow above).

## Live scraper tests

Tests marked `@pytest.mark.live` hit the real `play.limitlesstcg.com` site
and are skipped by default. They validate the Playwright CSS selectors in
`app/scraper/selectors.py`, which may drift if Limitless updates their
front end. To run them, set real credentials in `.env`:

```bash
cd backend
pytest -m live
```

Live tests are always skipped in CI.

## Next steps

- [Developer Guide](developer-guide.md) — contribution workflow, test
  structure, migrations.
- [Configuration](configuration.md) — full environment variable and
  admin-config reference.
- [API Reference](api.md) — every backend endpoint.
