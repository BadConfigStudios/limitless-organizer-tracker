# Prod Cutover + ArgoCD Migration — Design

**Date**: 2026-09-04
**Status**: Approved, pending plan

## Context

`limitless-production` (Fleet-managed) is currently down: `backend`,
`celery-beat`, `celery-worker` are `0/1` ready. Root cause: the repo was
repointed from `ghcr.io/genneteng/...` to `ghcr.io/badconfigstudios/...`
(#151), and the `badconfigstudios` GHCR packages are private. The
namespace has no working pull secret for that path, so the ReplicaSet
Fleet rolled out after the repoint sits in `ImagePullBackOff`, and k8s
fell back to the old ReplicaSet, which itself crash-loops (20k+ restarts
over 75 days — a separate, pre-existing problem never actually fixed).

`limitless-staging` was deployed by hand (`helm upgrade`, no GitOps
controller ever managed it) and never rolled to the new image path
either — but it's stable and holds the current, correct application
data. Per owner: staging's data is authoritative; old prod's is not.

Separately, the owner recorded a decision (2026-08-30) to move this
repo's GitOps from Fleet to ArgoCD — that DECISIONS.md entry currently
lives only on the still-open [PR #154](https://github.com/BadConfigStudios/limitless-organizer-tracker/pull/154)
(`docs/argocd-migration-decision`), not yet in `main`. **PR #154 is a
prerequisite: merge it before or alongside this work**, so `main`
actually carries the decision record this design relies on. ArgoCD
itself is already installed and running on the cluster (namespace
`argocd`), with a working reference deployment (`sparklab`) to model
this on.

## Goal

Single ArgoCD-managed production environment: namespace
`limitless-production` (freshly created), seeded with staging's current
database, no more Fleet involvement, no more staging environment.

## Non-goals

- Folding the app under `sparklab.badconfig.com` path routing / reusing
  its Google OIDC — floated, explicitly deferred (see
  `[[project_sparklab_future_migration]]` memory). This design only
  reuses the ArgoCD **project** grouping (`sparklab` AppProject), not
  sparklab's ingress path or auth.
- Fixing the chart-redraw bug in the Wait Time Estimator, the
  password-gated Admin tab, the 90-day default date window, or the
  Discord resubmit link — separate, parked work (see the earlier
  2026-09-04 brainstorm thread; resumes after this lands).
- Re-architecting the app itself. This is infra-only.

## Design

### ArgoCD Application

New `Application` in namespace `argocd`, modeled directly on the
existing `sparklab` Application:

- `metadata.name`: `limitless-organizer-tracker`
- `spec.project`: `sparklab` (existing AppProject — explicitly not
  `default`, per owner)
- `spec.source.repoURL`: this repo, `path: charts/limitless-organizer-tracker`,
  `targetRevision: main`
- `spec.destination.namespace`: `limitless-production` (new)
- `spec.syncPolicy.automated`: `{prune: true, selfHeal: true}`,
  `syncOptions: [CreateNamespace=true]`

### Image tagging + argocd-image-updater

`build-push.yml` currently tags images `latest` / short-sha / semver /
`pr-<n>`. Add a `main-<full 40-char sha>` tag (matches the pattern
`argocd-image-updater` already tracks for `sparklab`). Add annotations
to the new Application for each of backend/frontend/worker/docs:

```
argocd-image-updater.argoproj.io/<component>.allow-tags: regexp:^main-[0-9a-f]{40}$
argocd-image-updater.argoproj.io/<component>.helm.image-name: image.<component>.repository
argocd-image-updater.argoproj.io/<component>.helm.image-tag: image.<component>.tag
argocd-image-updater.argoproj.io/<component>.pull-secret: pullsecret:limitless-production/ghcr-pull-secret
argocd-image-updater.argoproj.io/<component>.update-strategy: newest-build
argocd-image-updater.argoproj.io/write-back-method: argocd
argocd-image-updater.argoproj.io/image-list: backend=ghcr.io/badconfigstudios/limitless-organizer-tracker/backend, frontend=..., worker=..., docs=...
```

This gives true continuous deploy: every push to `main` that touches
`backend/**`/`frontend/**`/`docs/**` builds, pushes a `main-<sha>` tag,
and the image updater bumps the Application automatically — no more
silently-stale `latest` pods.

### Pull secret

`ghcr-pull-secret` (`kubernetes.io/dockerconfigjson`) created in
`limitless-production`, reusing the same identity/token already backing
`sparklab-site`'s `ghcr-pull-secret`. That identity still needs explicit
per-package read access granted on each
`badconfigstudios/limitless-organizer-tracker/*` package — GHCR's
per-package permission model (same class of gotcha as the OpenTourney
GHCR-blocked issue) — reusing the token doesn't skip this step.

### Secrets delivery

`values.yaml`'s `secrets.*` block (`databaseUrl`, `celeryBrokerUrl`,
`celeryResultBackend`, `discordWebhookUrl`, `limitlessUsername`,
`limitlessPassword`, `apiKeys`) ships empty and renders into a k8s
`Secret` via `templates/secret.yaml`. Old prod/staging only got real
values through manual `helm upgrade --set …` — there is no
`values.production.yaml` in the repo, and none should be added (these
are real secrets, not committed to git). Instead, set them as
`spec.source.helm.parameters` directly on the **live** ArgoCD
Application object (applied via `kubectl`, never committed) — the same
pattern already used in-cluster for `sparklab`'s image-tag parameters.
Source the values from the current staging deployment's live secret
(`kubectl get secret ... -o jsonpath` for each key) rather than
inventing new ones, except where rotation is wanted.

### Fleet decommission

Delete the `limitless-production` `GitRepo` and `Bundle` in
`fleet-local` **before** deleting the old namespace (Sequencing step
1), not after ArgoCD starts syncing. Fleet's `syncPolicy` would
otherwise just recreate the namespace/resources it still owns the
moment they're deleted — the exact "fight over the same resources"
problem this section warns about, except with Fleet resurrecting things
ArgoCD is simultaneously trying to own.

### Ingress

Chart's ingress keeps the existing hostname
`limitless-org-dashboard.badconfig.com`, now backed by the new
namespace's services. No Cloudflare tunnel config change expected since
the hostname is unchanged — verify as part of cutover testing.

### Data migration

Staging's Percona PG data → new prod PGCluster:

1. Create `limitless-production` namespace + PGCluster (via the
   ArgoCD-synced chart) and let it reach a healthy empty state.
2. `pg_dump` from `limitless-staging`'s PG instance.
3. `pg_restore` into the new prod PG instance.
4. Spot-check row counts on key tables (`organizer`, `resubmission_event`,
   `organizer_activity`, `event_log`) against staging before cutover.

### Sequencing / safety

1. Delete the Fleet `GitRepo`/`Bundle` for `limitless-production`, then
   delete the old `limitless-production` namespace (broken, stale —
   owner confirmed no backup needed). Fleet must stop owning this
   namespace before it's deleted, or Fleet just recreates it.
2. Stand up new `limitless-production` via ArgoCD (empty DB), apply the
   `helm.parameters` secrets and the `ghcr-pull-secret`.
3. Migrate data from `limitless-staging` into it.
4. Verify new prod serving correctly end-to-end (manual verification
   gate — UI happy path + Resubmit Now + Discord notify, per
   `~/.claude/CLAUDE.md` Manual verification rule).
5. Only then delete `limitless-staging`.

`limitless-staging` is the only copy of current data until step 4
passes — kept alive as the safety net until the migration is verified,
even though old prod itself is discarded immediately (step 1).

## Testing / verification

- Backend: image builds successfully with new tag scheme (CI).
- Infra: ArgoCD Application reaches `Synced`/`Healthy` (mirrors sparklab
  Application status check).
- Manual verification gate before old staging is deleted: load the app
  at `limitless-org-dashboard.badconfig.com`, exercise Organizers tab,
  trigger "Resubmit Now", confirm Discord notification fires, confirm
  admin/diagnostics endpoints respond.

## Open risks

- Per-package GHCR access grant is a manual step outside this repo
  (org/package settings) — must be done before the pull secret works,
  regardless of which token backs it.
- `pg_dump`/`pg_restore` across Percona PGO clusters needs the right
  connection details (may require a temporary port-forward or a job
  run inside the cluster) — exact mechanics to be nailed down in the
  plan, not this design.
- PR #154 must land in `main` first (or this PR must be rebased onto
  it) so the ArgoCD-migration decision this design cites actually
  exists on the branch.
