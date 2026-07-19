# Staging Deployment

Staging deploys feature branches to the cube cluster (k3s on openSUSE
MicroOS) **before** they're merged to `main`, so changes are validated
against a real cluster, real Postgres, and real Redis prior to merge. This
is a manual `helm` workflow — staging is **not** managed by Fleet (see
[Helm Reference](helm.md#staging-vs-production) for why).

## Namespace & values

- Namespace: `limitless-staging`
- Helm values: `charts/limitless-organizer-tracker/values.staging.yaml`
  (layered on top of `values.yaml` — see [Helm Reference](helm.md))
- Public URL: `https://limitless-org-dashboard-staging.badconfig.com`
  (Cloudflare Tunnel — no port-forward needed)
- kubectl context: `mcgee-local` (or `mcgee-remote` if off-network and
  `mcgee-local` times out)

## Deploy workflow

Staging validation is a pre-merge gate — **do not merge to `main` before
deploying and verifying on staging.** Merging triggers the image
build/push workflow that tags `latest`, which production (via Fleet
GitOps) could pick up before you've actually confirmed the change works.

1. **Build images locally from the feature branch**, targeting the
   cluster's architecture:

   ```bash
   docker build --platform linux/amd64 -t ghcr.io/badconfigstudios/limitless-organizer-tracker/backend:<tag> ./backend
   docker build --platform linux/amd64 -t ghcr.io/badconfigstudios/limitless-organizer-tracker/frontend:<tag> ./frontend
   ```

2. **Push to GHCR**:

   ```bash
   docker push ghcr.io/badconfigstudios/limitless-organizer-tracker/backend:<tag>
   docker push ghcr.io/badconfigstudios/limitless-organizer-tracker/frontend:<tag>
   ```

3. **Update the running deployment's image tag** (rather than a full
   `helm upgrade`, for a quick iteration loop):

   ```bash
   kubectl --context mcgee-local -n limitless-staging set image \
     deployment/limitless-staging-backend backend=ghcr.io/badconfigstudios/limitless-organizer-tracker/backend:<tag>
   kubectl --context mcgee-local -n limitless-staging rollout status deployment/limitless-staging-backend
   ```

   Use `helm upgrade -f values.staging.yaml` instead when chart templates
   themselves changed (new env vars, new resources) — see
   [Helm Reference](helm.md) for the full command.

4. **Verify** at the staging URL via the Cloudflare Tunnel — no
   port-forward needed. Hit the changed UI/API surface directly; don't rely
   on automated tests alone (see the manual-verification checklist in
   [Developer Guide](../developer-guide.md)).

5. **Only then** open/merge the PR to `main`.

## Staging-specific values

From `values.staging.yaml`:

- `ingress.enabled: false` — staging is reached via the Cloudflare Tunnel
  pointed directly at the frontend/backend services, not an nginx Ingress.
- `percona.storageSize: 1Gi`, `percona.disableBackups: true` — smaller,
  no backup overhead for a disposable environment.
- `redis.master.persistence.size: 512Mi` — smaller than production's
  `1Gi`.
- `backend.env.LIMITLESS_APPLICATION_ID` is set to a staging-specific test
  application ID, distinct from production's.

## Known gotchas

- Fleet auto-discovers any `fleet.yaml` file recursively — the staging
  bundle is named `fleet-staging.yaml` specifically to avoid Fleet picking
  it up (staging is deployed manually, not via GitOps).
- Percona PG Operator v3 requires an explicit `spec.backups` section even
  when backups are disabled for staging.
- Passwords with special characters need URL-encoding in `DATABASE_URL`,
  and Alembic's configparser needs `%` escaped as `%%`.
