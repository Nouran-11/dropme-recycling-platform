# Security

This documents the security posture of the Drop Me platform: what was found,
what is actually fixed in this repository, what was consciously accepted for a
time-boxed challenge, and what real production hardening remains. It aims to be
honest — several items below are *not* fixed and are named as such.

## 1. Risks identified

Enumerated regardless of whether they are fixed. Status is one of
fixed / accepted / future.

| # | Risk | Status |
|---|------|--------|
| 1 | Containers running as root | fixed |
| 2 | Excess Linux capabilities / privilege escalation in containers | fixed |
| 3 | Writable container root filesystems | fixed where workable |
| 4 | Database/Redis reachable from outside the host | fixed |
| 5 | Grafana reachable from outside the host | fixed |
| 6 | SSH open to the internet | fixed (restricted to one /32) |
| 7 | Secrets committed to Git / Terraform state / tfvars | fixed |
| 8 | Secrets in the image or logs | fixed |
| 9 | Dependency CVEs shipped unnoticed | fixed (CI scan; 3 HIGH bumped) |
| 10 | Committed credentials in history | checked clean (Gitleaks, full history) |
| 11 | Malformed/abusive request bodies reaching the DB | fixed (layered validation) |
| 12 | API key comparison timing side-channel | fixed (`secrets.compare_digest`) |
| 13 | No transport encryption | fixed on deployment (Let's Encrypt); accepted locally |
| 14 | Application connects to Postgres as a superuser | accepted |
| 15 | Read endpoints (`GET /events`) are unauthenticated | accepted |
| 16 | `failure_reason` (internal exception text) exposed on the read API | accepted |
| 17 | Single shared API key, no per-machine identity or rotation | accepted |
| 18 | Grafana on default `admin` username | accepted |
| 19 | No rate limiting / no WAF | accepted |
| 20 | No container image signing / provenance | accepted |
| 21 | Log redaction matches exact key names only | accepted |
| 22 | Restore checksum covers `id`s, not full row contents | accepted |
| 23 | No point-in-time recovery (RPO = one backup interval) | accepted / future |
| 24 | No rollback via immutable release tags | accepted / future |
| 25 | Single host — no HA, manual patching | accepted / future |
| 26 | No local dependency audit tool run (`pip-audit` absent) | mitigated by CI Trivy |

## 2. Risks fixed (verifiable in this repo)

- **Non-root containers with fixed UIDs.** The API/worker image runs as UID
  `10001` (`app/Dockerfile`), the alert-sink as UID `10002`
  (`observability/alert-sink/Dockerfile`); frontend uses `nginx-unprivileged`
  (UID 101). Fixed UIDs are stable across rebuilds and match the intended
  runtime identity.
- **Dropped capabilities and no privilege escalation.** Every application,
  gateway, and observability service in `docker-compose.yml` sets
  `cap_drop: [ALL]` and `security_opt: [no-new-privileges:true]`. Caddy re-adds
  only `NET_BIND_SERVICE` so it can bind low ports.
- **Read-only root filesystems where workable.** `api`, `worker`, and
  `alert-sink` run `read_only: true` with a `tmpfs` for `/tmp`. Services that
  must write (Postgres, Grafana, Prometheus, Caddy's cert store) use named
  volumes rather than a writable root, and are not marked read-only.
- **No exposed data or admin ports locally.** In `docker-compose.yml` only Caddy
  publishes a port (`80`); Postgres, Redis, the API, the worker, and the
  frontend publish nothing. Grafana is bound to `127.0.0.1:3000` only.
- **Locked-down network on EC2.** The security group in `deploy/terraform/main.tf`
  opens `80` and `443` to `0.0.0.0/0`, and `22` only to the `my_ip` /32 variable.
  Nothing else is inbound; Grafana stays on `127.0.0.1` and is never exposed.
- **Secrets never in Git, tfvars, or Terraform state.** `.env` is gitignored;
  `deploy/terraform/user_data.sh.tftpl` generates `POSTGRES_PASSWORD`, `API_KEY`,
  and the Grafana password with `openssl rand` **on the instance** and writes
  them to `.env` under `umask 077`. No secret is an input variable, so none can
  reach `terraform.tfvars` or state. `terraform.tfvars`, `*.tfstate*`, and
  `.terraform/` are gitignored.
- **No secrets in the image or logs.** The Dockerfile bakes in no secrets; the
  user-data script deliberately omits `set -x` so generated secrets do not land
  in cloud-init logs. Structured logging redacts by key name
  (`app/src/dropme/logging.py`), and the middleware logs method/path/status
  only — never bodies or headers. Redaction of the API key was verified live:
  a request carrying `X-API-Key` produced JSON logs with no occurrence of the
  key value.
- **Config fails fast on missing secrets.** `dropme.config` has no defaults for
  `DATABASE_URL`, `REDIS_URL`, or `API_KEY`, and `docker-compose.yml` uses
  `${VAR:?...}` guards so the stack refuses to start with a secret unset rather
  than booting misconfigured.
- **Dependency scanning in CI.** `.github/workflows/pr.yml` runs `trivy fs`
  (fail on HIGH/CRITICAL with a fix available) and `gitleaks`. Trivy caught
  three HIGH CVEs in the transitive `starlette` pulled by FastAPI
  (CVE-2025-62727, CVE-2026-48818, CVE-2026-54283); they were fixed by bumping
  FastAPI/starlette (`chore(deps): bump fastapi/starlette to clear HIGH CVEs`).
- **No committed secrets in history.** A full-history Gitleaks scan (42 commits)
  found no leaks — see `evidence/08-security/gitleaks-full-history.txt`.
- **Input validation at the edge with a DB backstop.** `app/src/dropme/schemas.py`
  rejects bad enums, out-of-range `item_count`, blank `machine_id`, naive
  timestamps, and far-future timestamps with a 422; the same invariants exist as
  Postgres `CHECK` constraints and enum types in the migration, so a bug that
  bypasses the API layer still cannot write invalid data.
- **Constant-time API key check.** `require_api_key` compares with
  `secrets.compare_digest` (`app/src/dropme/main.py`), avoiding a timing
  side-channel on the shared key.
- **TLS on the deployment.** The deploy Caddyfile (`proxy/Caddyfile.deploy`) runs
  with auto_https on and serves `<eip>.sslip.io`, so Caddy provisions a real
  Let's Encrypt certificate and terminates HTTPS with HSTS.
- **Security headers at the edge.** Caddy strips `Server` and sets
  `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, and a
  `Content-Security-Policy` on every response (local and deploy Caddyfiles).

## 3. Risks accepted for this challenge

- **HTTP, not TLS, locally.** The local stack serves plain HTTP on port 80;
  there is no local domain to certify. TLS exists only on the EC2 deployment.
- **The application connects to Postgres as a superuser.** `DATABASE_URL` uses
  the `POSTGRES_USER` role, which the Postgres image creates as a superuser. The
  app therefore has more privilege than it needs. A dedicated least-privilege
  role that owns only the `events` table is deferred (see future work) — this is
  called out rather than claimed as least-privilege.
- **Read endpoints are unauthenticated.** Only writes (`POST /events`) require
  `X-API-Key`. `GET /events` and `GET /events/{id}` are public, which also means
  the `failure_reason` field is world-readable.
- **`failure_reason` exposes internal detail.** Worker exception text (truncated
  to 500 chars) is stored and returned by the read API. An exception carrying
  internal detail would leak to any caller. Production would map failures to a
  coarse code and keep detail in logs only.
- **Single shared API key.** One key authorizes all writers; there is no
  per-machine credential, no rotation, and no revocation of an individual device.
- **Grafana uses the default `admin` username** (random password on EC2, but
  `admin`/`admin` locally). It is only ever reachable on `127.0.0.1`, never on
  the public edge, which is why this is accepted rather than fixed.
- **No rate limiting and no WAF.** The API will accept unbounded request volume;
  abuse controls are out of scope at this size.
- **No image signing or provenance.** Images are built and run without cosign
  signatures or SBOM attestation on the deployed artifact.
- **Redaction matches exact key names only.** `logging.py` redacts a fixed set of
  sensitive keys; a secret logged under an unlisted key, or embedded inside a
  larger string, would not be caught. The mitigating control is that the code
  never logs bodies/headers in the first place.
- **Restore verification checksums `id`s, not full rows.** `verify_restore.sh`
  compares count, `min`/`max(created_at)`, and an md5 over the ordered `id` list.
  A corrupted column value on a surviving row would pass. Named, not hidden.
- **No local dependency audit was run.** `pip-audit` is not installed in this
  environment, so no separate local audit was performed. Dependency scanning is
  covered by `trivy fs` against `uv.lock` in CI — this doc does not claim a local
  audit occurred.

## 4. Risks requiring future work

- **Per-machine identity instead of a shared key.** mTLS or signed device tokens
  per reverse-vending machine, with rotation and per-device revocation.
- **A managed secret store.** AWS Secrets Manager or the External Secrets
  Operator instead of an on-instance `.env`, so secrets are versioned, rotated,
  and audited rather than living as a file on one host.
- **Least-privilege database role.** An application role that owns nothing it
  does not need and is not a superuser, replacing the current superuser
  connection.
- **Point-in-time recovery.** WAL archiving with `wal-g` or `pgBackRest` to drop
  RPO from one backup interval to seconds, plus versioned object storage with
  lifecycle rules instead of a local volume.
- **Immutable release tags + registry, enabling tag-based rollback.** The current
  build-from-source deployment rolls back by checking out a prior commit and
  rebuilding; a registry with `sha`/`vX.Y.Z` tags would make "which version is
  running" answerable and rollback atomic.
- **Image signing and audit logging.** cosign-signed images with verification at
  deploy, and an audit trail for administrative actions.
- **Coarse error mapping** so the read API never returns internal exception text.
- **Rate limiting / WAF** at the edge, and stricter response headers where the
  static frontend allows dropping `unsafe-inline`.
