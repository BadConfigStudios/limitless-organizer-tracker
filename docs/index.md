# Limitless Organizer Tracker

Limitless Organizer Tracker is an always-running service that does two
things for a [Limitless TCG](https://play.limitlesstcg.com) tournament
organizer:

1. **Tracks an organizer-application's status** on a schedule, sends a
   Discord reminder 1–2 times a day to take advantage of Limitless's
   LIFO-favoring review process, and lets the user trigger a manual
   resubmission (which notifies a Discord channel on completion).
2. **Tracks platform-wide organizer onboarding activity** — ingesting
   tournament data to determine when organizers across all games become
   active, fitting a regression to the onboarding rate, and projecting how
   long a new applicant should expect to wait.

## Who it's for

Built for an individual running their own Limitless tournament organizer
application, who also wants visibility into how fast Limitless onboards new
organizers platform-wide (to set expectations for their own pending
application). This is a small personal tool — single set of credentials,
single Discord webhook — not a multi-tenant SaaS product.

## High-level architecture

- **Backend**: FastAPI + SQLAlchemy + Celery (worker + beat) + PostgreSQL +
  Redis.
- **Scraper**: Playwright-driven login/status-check/resubmit against
  `play.limitlesstcg.com`; a separate `httpx`-only path probes public
  organizer profile pages (no login required) to detect onboarding.
- **Frontend**: React + TypeScript dashboard (Vite), built on TanStack Query.
- **Deployment**: Docker Compose locally; Helm chart + Rancher Fleet GitOps
  to a k3s cluster for staging/production.

See [Architecture](architecture.md) for the full system diagram and data
flow, and [Requirements](requirements.md) for the complete business/
functional/non-functional requirement traceability table.

## Where to go next

- New to the project? Start with [Getting Started](getting-started.md).
- Contributing code? Read the [Developer Guide](developer-guide.md).
- Looking for an endpoint? See the [API Reference](api.md).
- Deploying somewhere? See [Deployment](deployment/local.md).
