# Prod Cutover + ArgoCD Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken, Fleet-managed `limitless-production` with a fresh, ArgoCD-managed prod in namespace `limitless-production`, seeded with `limitless-staging`'s current database, with Fleet and the old staging environment fully retired.

**Architecture:** New k8s namespace `limitless-production`, deployed by a new ArgoCD `Application` (`project: sparklab`) syncing this repo's existing Helm chart. Secrets and image tags are supplied as `helm.parameters` set directly on the live Application object (never committed to git), mirroring the working `sparklab` Application already on-cluster. Database migrates via `pg_dump`/`pg_restore` from staging's Percona PG cluster into a fresh one in the new namespace.

**Tech Stack:** Helm chart `charts/limitless-organizer-tracker`, ArgoCD + argocd-image-updater, Percona PostgreSQL Operator (PGO) v2, GitHub Actions (`build-push.yml`), GHCR (private packages).

## Global Constraints

- Never commit real secret values to git — `secrets.*` Helm values stay empty in `values.yaml`; real values go on the live ArgoCD `Application` object only (`kubectl apply`, not tracked in this repo).
- `spec.project: sparklab` on the new Application — not `default`.
- Namespace deletions (old `limitless-production`, later `limitless-staging`) each require explicit owner confirmation immediately before running, even though the overall plan is pre-approved — per `~/.claude/CLAUDE.md`, approval doesn't carry forward across separate irreversible actions.
- `limitless-staging` stays alive until Task 7 (manual verification) passes — it's the only copy of current data until then.
- kubectl context: `mcgee-remote` (per project memory — `mcgee-local` isn't reachable off-network).

---

### Task 1: Merge PR #154 (ArgoCD decision record)

**Files:** none in this repo (owner action on GitHub)

- [ ] **Step 1: Confirm PR #154 is mergeable**

```bash
gh pr view 154 --repo BadConfigStudios/limitless-organizer-tracker --json state,mergeable
```
Expected: `"state": "OPEN"`, `"mergeable": "MERGEABLE"`

- [ ] **Step 2: Owner merges PR #154** (Claude must not run `gh pr merge` without explicit in-the-moment approval, per `~/.claude/CLAUDE.md`)

- [ ] **Step 3: Verify the decision record landed on `main`**

```bash
git fetch origin main && git show origin/main:DECISIONS.md | grep -A3 "Migrate deployment from Fleet to ArgoCD"
```
Expected: the 2026-08-30 entry text appears.

---

### Task 2: Repo changes — image tagging + Fleet cleanup

**Files:**
- Modify: `.github/workflows/build-push.yml` (each of `build-backend`, `build-worker`, `build-frontend`, `build-docs` jobs' `docker/metadata-action` step)
- Delete: `fleet.yaml`

**Interfaces:**
- Produces: images pushed to `ghcr.io/badconfigstudios/limitless-organizer-tracker/{backend,worker,frontend,docs}` also carry a `main-<40-char-sha>` tag on every push to `main`, consumed by Task 5's `argocd-image-updater` annotations (`regexp:^main-[0-9a-f]{40}$`).

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull --ff-only
git checkout -b infra/argocd-image-tagging
```

- [ ] **Step 2: Add the `main-<sha>` tag to each image's metadata step**

In `.github/workflows/build-push.yml`, each `uses: docker/metadata-action@v5` block currently has a `tags:` list like:

```yaml
        tags: |
          type=semver,pattern={{version}}
          type=sha
          type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
          type=ref,event=pr
```

Add one line to each of the four blocks (backend/worker/frontend/docs):

```yaml
          type=raw,value=main-${{ github.sha }},enable=${{ github.ref == 'refs/heads/main' }}
```

`github.sha` is the full 40-character commit SHA (unlike metadata-action's `type=sha` shorthand, which truncates to 7).

- [ ] **Step 3: Remove the now-obsolete Fleet bundle definition**

```bash
git rm fleet.yaml
```

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/build-push.yml
git commit -m "infra: tag images main-<sha> for argocd-image-updater, drop Fleet bundle

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push -u origin infra/argocd-image-tagging
```

- [ ] **Step 5: Open PR, run /review, get it merged**

```bash
gh pr create --title "infra: image tagging for ArgoCD + drop Fleet bundle" --body "$(cat <<'EOF'
## Summary
- Adds a `main-<full-sha>` image tag on every push to main, so argocd-image-updater can track new builds (mirrors the existing `sparklab` Application's tagging convention).
- Removes `fleet.yaml` — Fleet no longer manages this repo's deployment (see docs/superpowers/specs/2026-09-04-prod-cutover-argocd-design.md).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Then run `/review`, fix any Critical/High or low-LOE findings, and get owner merge approval (never self-merge).

- [ ] **Step 6: Verify a real build produces the new tag** (after merge to main)

```bash
gh run list --repo BadConfigStudios/limitless-organizer-tracker --workflow=build-push.yml --limit 1
gh api /orgs/badconfigstudios/packages/container/limitless-organizer-tracker%2Fbackend/versions --jq '.[0].metadata.container.tags'
```
Expected: a tag matching `main-[0-9a-f]{40}` in the list.

---

### Task 3: Decommission Fleet, delete old prod namespace

**Files:** none (cluster-only)

- [ ] **Step 1: Confirm with owner immediately before running** — this deletes the broken old prod namespace. (Pre-authorized in the design spec, but confirm again right before executing, per `~/.claude/CLAUDE.md`.)

- [ ] **Step 2: Delete the Fleet GitRepo and Bundle** (must happen before namespace deletion, or Fleet recreates it)

```bash
kubectl --context mcgee-remote delete bundle limitless-production -n fleet-local
kubectl --context mcgee-remote delete gitrepo limitless-production -n fleet-local
```
Expected: both `deleted`.

- [ ] **Step 3: Verify Fleet no longer tracks this app**

```bash
kubectl --context mcgee-remote get gitrepo,bundle -n fleet-local 2>&1 | grep -i limitless
```
Expected: no output.

- [ ] **Step 4: Delete the old `limitless-production` namespace**

```bash
kubectl --context mcgee-remote delete namespace limitless-production
```
Expected: `namespace "limitless-production" deleted` (may take a minute — PGO/pgbackrest finalizers).

- [ ] **Step 5: Verify it's gone**

```bash
kubectl --context mcgee-remote get ns limitless-production
```
Expected: `Error from server (NotFound)`.

---

### Task 4: Create new namespace, pull secret, PG cluster

**Files:** none (cluster-only)

- [ ] **Step 1: Owner grants per-package GHCR access** (manual, outside this repo — GitHub org UI: each `badconfigstudios/limitless-organizer-tracker/{backend,worker,frontend,docs}` package → Package settings → Manage Actions access / collaborators → grant read to whichever identity backs `sparklab-site`'s `ghcr-pull-secret`)

- [ ] **Step 2: Create the namespace**

```bash
kubectl --context mcgee-remote create namespace limitless-production
```

- [ ] **Step 3: Copy the pull secret from `sparklab-site`**

```bash
kubectl --context mcgee-remote get secret ghcr-pull-secret -n sparklab-site -o json \
  | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp) | .metadata.namespace="limitless-production"' \
  | kubectl --context mcgee-remote apply -f -
```

- [ ] **Step 4: Verify the secret exists and decodes to a valid dockerconfigjson**

```bash
kubectl --context mcgee-remote -n limitless-production get secret ghcr-pull-secret -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq '.auths | keys'
```
Expected: `["ghcr.io"]`

- [ ] **Step 5: Verify the granted identity can actually pull** (dry-run against one image)

```bash
kubectl --context mcgee-remote run pull-test --image=ghcr.io/badconfigstudios/limitless-organizer-tracker/backend:latest \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"ghcr-pull-secret"}]}}' -n limitless-production --restart=Never --command -- sleep 5
kubectl --context mcgee-remote -n limitless-production get pod pull-test -o jsonpath='{.status.phase}'
kubectl --context mcgee-remote -n limitless-production delete pod pull-test
```
Expected: phase is `Running` or `Succeeded`, not stuck in `ImagePullBackOff` — check with `kubectl get pod pull-test -o jsonpath='{.status.containerStatuses[0].state}'` if unclear.

---

### Task 5: Apply the ArgoCD Application

**Files:** none (cluster-only — Application object applied directly, matching how `sparklab`'s Application was set up)

**Interfaces:**
- Consumes: `main-<sha>` tags from Task 2, `ghcr-pull-secret` from Task 4.

- [ ] **Step 1: Read staging's non-DB secret values** (Discord webhook, Limitless creds, API keys — these carry over as-is; DB/broker URLs do not, they're rebuilt for the new namespace in Step 2)

```bash
for k in DISCORD_WEBHOOK_URL LIMITLESS_USERNAME LIMITLESS_PASSWORD API_KEYS; do
  echo "$k=$(kubectl --context mcgee-remote -n limitless-staging get secret limitless-staging-limitless-organizer-tracker-secrets -o jsonpath="{.data.$k}" | base64 -d)"
done
```
Keep this output for Step 3 — do not paste it into the repo or a PR.

- [ ] **Step 2: Write the Application manifest to a local scratch file** (not committed — apply directly)

```bash
cat > /tmp/limitless-argocd-app.yaml <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: limitless-organizer-tracker
  namespace: argocd
  annotations:
    argocd-image-updater.argoproj.io/image-list: |
      backend=ghcr.io/badconfigstudios/limitless-organizer-tracker/backend,
      worker=ghcr.io/badconfigstudios/limitless-organizer-tracker/worker,
      frontend=ghcr.io/badconfigstudios/limitless-organizer-tracker/frontend,
      docs=ghcr.io/badconfigstudios/limitless-organizer-tracker/docs
    argocd-image-updater.argoproj.io/backend.allow-tags: regexp:^main-[0-9a-f]{40}$
    argocd-image-updater.argoproj.io/backend.helm.image-name: image.backend.repository
    argocd-image-updater.argoproj.io/backend.helm.image-tag: image.backend.tag
    argocd-image-updater.argoproj.io/backend.pull-secret: pullsecret:limitless-production/ghcr-pull-secret
    argocd-image-updater.argoproj.io/backend.update-strategy: newest-build
    argocd-image-updater.argoproj.io/worker.allow-tags: regexp:^main-[0-9a-f]{40}$
    argocd-image-updater.argoproj.io/worker.helm.image-name: image.worker.repository
    argocd-image-updater.argoproj.io/worker.helm.image-tag: image.worker.tag
    argocd-image-updater.argoproj.io/worker.pull-secret: pullsecret:limitless-production/ghcr-pull-secret
    argocd-image-updater.argoproj.io/worker.update-strategy: newest-build
    argocd-image-updater.argoproj.io/frontend.allow-tags: regexp:^main-[0-9a-f]{40}$
    argocd-image-updater.argoproj.io/frontend.helm.image-name: image.frontend.repository
    argocd-image-updater.argoproj.io/frontend.helm.image-tag: image.frontend.tag
    argocd-image-updater.argoproj.io/frontend.pull-secret: pullsecret:limitless-production/ghcr-pull-secret
    argocd-image-updater.argoproj.io/frontend.update-strategy: newest-build
    argocd-image-updater.argoproj.io/docs.allow-tags: regexp:^main-[0-9a-f]{40}$
    argocd-image-updater.argoproj.io/docs.helm.image-name: image.docs.repository
    argocd-image-updater.argoproj.io/docs.helm.image-tag: image.docs.tag
    argocd-image-updater.argoproj.io/docs.pull-secret: pullsecret:limitless-production/ghcr-pull-secret
    argocd-image-updater.argoproj.io/docs.update-strategy: newest-build
    argocd-image-updater.argoproj.io/write-back-method: argocd
spec:
  project: sparklab
  destination:
    server: https://kubernetes.default.svc
    namespace: limitless-production
  source:
    repoURL: https://github.com/BadConfigStudios/limitless-organizer-tracker.git
    targetRevision: main
    path: charts/limitless-organizer-tracker
    helm:
      releaseName: limitless
      parameters:
        - name: secrets.databaseUrl
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.celeryBrokerUrl
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.celeryResultBackend
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.discordWebhookUrl
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.limitlessUsername
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.limitlessPassword
          value: "REPLACE_ME"
          forceString: true
        - name: secrets.apiKeys
          value: "REPLACE_ME"
          forceString: true
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
YAML
```

`secrets.databaseUrl`/`celeryBrokerUrl`/`celeryResultBackend` are **not** copied from staging — they must point at the new namespace's own Postgres/Redis services (the whole point of a separate DB per environment). Once Task 6's PGCluster + Redis are up in `limitless-production`, construct them as:
- `databaseUrl`: `postgresql://limitless:<password>@limitless-pg-primary.limitless-production.svc:5432/limitless_tracker` — get `<password>` via `kubectl --context mcgee-remote -n limitless-production get secret limitless-pg-pguser-limitless -o jsonpath='{.data.password}' | base64 -d` once the PGCluster exists.
- `celeryBrokerUrl` / `celeryResultBackend`: `redis://limitless-redis-master.limitless-production.svc:6379/0` and `/1` respectively (matches `values.yaml`'s existing `redis://localhost:6379/0`-style default pattern, just pointed at the in-cluster service).

Fill in the four carried-over values (`discordWebhookUrl`, `limitlessUsername`, `limitlessPassword`, `apiKeys`) from Step 1's output, and the three rebuilt ones once available, replacing every `REPLACE_ME` in the file before applying.

- [ ] **Step 3: Apply it**

```bash
kubectl --context mcgee-remote apply -f /tmp/limitless-argocd-app.yaml
rm /tmp/limitless-argocd-app.yaml
```

- [ ] **Step 4: Verify sync status**

```bash
kubectl --context mcgee-remote get application limitless-organizer-tracker -n argocd -o jsonpath='{.status.sync.status} {.status.health.status}{"\n"}'
```
Expected: `Synced Healthy` (may take a couple of sync cycles — re-run after a minute if not).

- [ ] **Step 5: Verify pods are actually running**

```bash
kubectl --context mcgee-remote -n limitless-production get pods
```
Expected: backend/frontend/celery-worker/celery-beat all `1/1 Running` (DB-dependent ones may crash-loop until Task 6's data migration completes — that's expected at this point).

---

### Task 6: Migrate data from staging to new prod

**Files:** none (cluster-only)

**Interfaces:**
- Consumes: `limitless-pg` PGCluster running in `limitless-production` (from Task 5).

- [ ] **Step 1: Dump staging's database**

```bash
kubectl --context mcgee-remote -n limitless-staging exec -i limitless-staging-pg-instance1-8zpd-0 -c database -- \
  pg_dump -U limitless -d limitless_tracker --format=custom --file=/tmp/staging_dump.pgcustom
kubectl --context mcgee-remote -n limitless-staging cp limitless-staging-pg-instance1-8zpd-0:/tmp/staging_dump.pgcustom \
  /tmp/staging_dump.pgcustom -c database
```
(Pod name `limitless-staging-pg-instance1-8zpd-0` confirmed via `kubectl -n limitless-staging get pods | grep pg-instance1` — re-check in case it's changed by the time this runs.)

- [ ] **Step 2: Restore into the new prod database**

```bash
NEW_PG_POD=$(kubectl --context mcgee-remote -n limitless-production get pods -l postgres-operator.crunchydata.com/role=primary -o jsonpath='{.items[0].metadata.name}')
kubectl --context mcgee-remote -n limitless-production cp /tmp/staging_dump.pgcustom "$NEW_PG_POD:/tmp/staging_dump.pgcustom" -c database
kubectl --context mcgee-remote -n limitless-production exec -i "$NEW_PG_POD" -c database -- \
  pg_restore -U limitless -d limitless_tracker --clean --if-exists /tmp/staging_dump.pgcustom
```

- [ ] **Step 3: Spot-check row counts match staging**

```bash
for tbl in organizer resubmission_event organizer_activity event_log; do
  echo "-- $tbl --"
  echo "staging: $(kubectl --context mcgee-remote -n limitless-staging exec -i limitless-staging-pg-instance1-8zpd-0 -c database -- psql -U limitless -d limitless_tracker -tAc "select count(*) from $tbl")"
  echo "prod:    $(kubectl --context mcgee-remote -n limitless-production exec -i "$NEW_PG_POD" -c database -- psql -U limitless -d limitless_tracker -tAc "select count(*) from $tbl")"
done
```
Expected: matching counts for every table.

- [ ] **Step 4: Restart backend/worker/beat so they pick up a healthy DB connection**

```bash
kubectl --context mcgee-remote -n limitless-production rollout restart deployment limitless-limitless-organizer-tracker-backend limitless-limitless-organizer-tracker-celery-worker limitless-limitless-organizer-tracker-celery-beat
kubectl --context mcgee-remote -n limitless-production rollout status deployment limitless-limitless-organizer-tracker-backend
```
Expected: rollout completes, pod `1/1 Running`.

---

### Task 7: Manual verification gate (before deleting staging)

**Files:** none

- [ ] **Step 1: Repoint the ingress hostname if needed** — check whether the chart's ingress in the new namespace already claims `limitless-org-dashboard.badconfig.com`:

```bash
kubectl --context mcgee-remote -n limitless-production get ingress -o jsonpath='{.items[0].spec.rules[0].host}'
```
Expected: `limitless-org-dashboard.badconfig.com`. If the old namespace's ingress object still exists somehow, that'd conflict — Task 3 already deleted the whole old namespace, so this should be clean.

- [ ] **Step 2: Print the verification checklist, then work through it**

- [ ] Dashboard loads at `https://limitless-org-dashboard.badconfig.com`
- [ ] Organizers tab renders activity chart with real (migrated) data
- [ ] Application tab shows current status, not empty/error
- [ ] "Resubmit Now" button triggers successfully (check `/api/tasks/resubmit-application` response and the resulting Discord message)
- [ ] Admin tab: Diagnostics, Task Triggers, Configuration, Event Log all load without errors
- [ ] `curl -H "X-API-Key: <key>" https://limitless-org-dashboard.badconfig.com/api/organizers/highest-id` returns the expected highest organizer ID (compare against the value from `[[project_organizer_id_context]]` memory — should be ≥ 2742)

- [ ] **Step 3: Report pass/fail per item.** Fix any failures with follow-up commits/cluster changes before proceeding to Task 8.

---

### Task 8: Delete staging

**Files:** none

- [ ] **Step 1: Confirm with owner immediately before running** — Task 7 must have fully passed first.

- [ ] **Step 2: Delete the namespace**

```bash
kubectl --context mcgee-remote delete namespace limitless-staging
```

- [ ] **Step 3: Verify it's gone**

```bash
kubectl --context mcgee-remote get ns limitless-staging
```
Expected: `Error from server (NotFound)`.

- [ ] **Step 4: Update project memory** — record the new deployment topology (single `limitless-production`, ArgoCD-managed, `sparklab` project) replacing the stale Fleet/staging+prod description in `[[project_deployment_target]]`.
