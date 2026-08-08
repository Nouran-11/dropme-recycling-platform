# Drop Me Recycling Platform

Event ingestion and processing platform for reverse-vending machines. Machines
post deposit events; the API validates and persists them and returns
immediately; a worker processes each event asynchronously (computing an
estimated weight) so ingestion is never blocked by processing. The whole thing
runs as one Docker Compose stack locally and on a single EC2 instance.

![Architecture](docs/architecture.png)

Trust boundaries: the **public edge** (Caddy) is the only thing that publishes a
port; the **internal service network** holds the API, worker, and observability;
the **data tier** holds Redis and Postgres, which are never exposed.

## Quickstart

**Prerequisites:** Docker with the Compose plugin, and GNU `make`. (For the test
suite and local Alembic commands you also need [`uv`](https://docs.astral.sh/uv/)
and Python 3.12.)

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, API_KEY, and GF_SECURITY_ADMIN_PASSWORD
# (all three are required — Compose refuses to start if any is unset or empty),
# and make DATABASE_URL use the same user/password, e.g.:
#   DATABASE_URL=postgresql+psycopg://dropme:<password>@postgres:5432/dropme
#   POSTGRES_USER=dropme
make up
```

`make up` builds the images and blocks until every container is healthy
(`docker compose up -d --build --wait`). Expected result: ten services
(`caddy`, `frontend`, `api`, `worker`, `postgres`, `redis`, `prometheus`,
`alertmanager`, `alert-sink`, `grafana`) reporting healthy, with `migrate`
having exited 0. Then:

```bash
open http://localhost                     # UI lists events (empty at first)
curl -X POST http://localhost/api/events \
  -H "X-API-Key: <your API_KEY>" -H 'content-type: application/json' \
  -d '{"machine_id":"kiosk-1","material_type":"ALU","item_count":6,"event_timestamp":"2026-08-08T09:00:00+00:00"}'
```

The event returns `201` immediately with `status: received`; within a second the
worker moves it to `processed` with an `estimated_weight_g`.

## Configuration

Every variable is read from the environment (via `.env` locally). The app fails
fast if `DATABASE_URL`, `REDIS_URL`, or `API_KEY` is missing.

| Variable | What it does | Secret | Default | Used by |
|---|---|---|---|---|
| `DATABASE_URL` | SQLAlchemy/psycopg connection URL | yes | — (required) | api, worker, migrate |
| `REDIS_URL` | Redis connection URL (queue) | no | — (required) | api, worker |
| `API_KEY` | Key required on `POST /events` (`X-API-Key`) | yes | — (required) | api |
| `POSTGRES_USER` | Postgres role (also the app's DB user) | no | — (required) | postgres, backup |
| `POSTGRES_PASSWORD` | Postgres password | yes | — (required) | postgres |
| `POSTGRES_DB` | Database name | no | `dropme` | postgres, backup |
| `VERSION` | Build version → `/version`, `dropme_build_info` | no | `0.0.0-dev` | build arg, api |
| `GIT_SHA` | Build commit → `/version`, `dropme_build_info` | no | `unknown` | build arg, api |
| `BUILT_AT` | Build timestamp → `/version` | no | `unknown` | build arg, api |
| `LOG_LEVEL` | structlog level | no | `INFO` | api, worker |
| `GF_SECURITY_ADMIN_USER` | Grafana admin username | no | `admin` | grafana |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | yes | — (required) | grafana |
| `BACKUP_INTERVAL` | Seconds between automatic backups | no | `3600` | backup |
| `SITE_ADDRESS` | Public hostname for TLS (deploy only) | no | — (set by EC2 user-data) | caddy (deploy) |

`.env` is gitignored and never committed. On EC2 it is generated on the instance
with `openssl rand` — no secret lives in Git, tfvars, or Terraform state.

## Running tests

The suite (28 tests) needs a Postgres and a Redis reachable on `localhost` with
the credentials `conftest.py` sets by default:
`postgresql+psycopg://postgres:postgres@localhost:5432/dropme_test` and
`redis://localhost:6379/0`. Without them you get ~28 identical connection
errors. Bring up throwaway instances:

```bash
docker run -d --name test-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=dropme_test -p 5432:5432 postgres:16-bookworm
docker run -d --name test-redis -p 6379:6379 redis:7-alpine

make test          # cd app && uv run pytest -q
make lint          # ruff check
```

CI (`.github/workflows/pr.yml`) runs the same suite against Postgres/Redis
service containers, plus `ruff format --check`, a docker build, `trivy fs`, and
`gitleaks`.

## Database and migrations

The schema is a single `events` table with two enums (`material_type`,
`event_status`), `CHECK` constraints mirroring the API validation, two indexes,
and an `updated_at` trigger. Migrations are versioned with Alembic
(`app/migrations/`); the URL comes only from `DATABASE_URL`, never `alembic.ini`.

```bash
make migrate                       # one-shot: alembic upgrade head (via compose)
cd app && uv run alembic downgrade -1   # step back one migration
make seed                          # insert ~200 sample events (stack must be up)
```

## Building images

One image serves both the API and the worker (different `command`), so there is
one thing to build, scan, version, and roll back — see `app/Dockerfile`
(multi-stage, non-root UID 10001, base images pinned by digest). The frontend is
a separate static-nginx image. Build args `VERSION`/`GIT_SHA`/`BUILT_AT` are
baked into the image at build time.

```bash
make build          # docker compose build (local)
```

**Tagging scheme.** The three workflows map to the three kinds of change:

| Trigger | Workflow | Image action |
|---|---|---|
| Pull request | `pr.yml` | image is **built to prove it compiles, never pushed** |
| Push to `main` | `main.yml` | multi-arch build pushed to GHCR as `sha-<short>` and `main` |
| Tag `v*` | `release.yml` | multi-arch build pushed as `v<version>` and `sha-<short>`, plus a GitHub Release |

Images are **never tagged `:latest`**. A moving `:latest` makes "which version
is running?" unanswerable — two hosts pulling `:latest` a day apart can run
different code with no way to tell. Every pushed image instead carries an
immutable `sha-<short>` (and, for releases, `v<version>`), so a tag names exactly
one build.

**Determining the running version.** `GET /version` returns `{version, git_sha,
built_at}`, and the same identity is exposed as the Prometheus gauge
`dropme_build_info{version, git_sha}` (visible on the "Is it up?" dashboard row).
That is what lets you answer "did failures begin after a specific release?".

**Honest caveat about the deployment.** The EC2 instance currently **builds from
source on the host** (see `deploy/terraform/user_data.sh.tftpl`); it does **not**
pull these GHCR images. Its generated `.env` sets a hardcoded `VERSION=0.1.0`
alongside the real deployed commit, so `GET /version` on the host reports
`version=0.1.0` with the actual `git_sha` — not a `v<version>` tied to a release.
Making the deployment pull the released image (so `/version` matches a release
tag) is future work.

## Deploying to AWS and rolling back

A single `t3.medium` runs the identical compose stack, provisioned by Terraform
in `deploy/terraform/` (default VPC, Elastic IP, 30 GB gp3, security group
opening 80/443 to the world and 22 to your IP only). The instance installs
Docker, clones this repo, generates `.env`, and runs the stack with the
deployment override (`docker-compose.deploy.yml`), which turns on Caddy's
auto-HTTPS for `<eip>.sslip.io` (a real Let's Encrypt cert).

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # set my_ip and key_name
terraform init && terraform plan && terraform apply
terraform output url                           # https://<eip>.sslip.io
```

**Rollback** (no registry/tags, so it is source-based): `ssh` in,
`git checkout <previous-sha>`, and rebuild — full steps in
[RUNBOOK.md#rollback](RUNBOOK.md#rollback). Confirm the change via
`/api/version`.

## Observability

Grafana serves one dashboard, **"Drop Me — Platform Health"**, with rows in
incident-triage order:

1. **Is it up?** — `up` per service, dependency reachability, running build.
2. **Is it failing?** — request rate, 5xx rate, p95/p99 latency.
3. **Is processing keeping up?** — created vs processed rate, **oldest
   unprocessed event age** (the headline metric), queue depth, job failures.

Three alerts (`observability/prometheus/alerts.yml`) route through Alertmanager
to the `alert-sink` container, which logs each payload to stdout so delivery is
provable without any external account:

- **EventProcessingLag** — oldest unprocessed age > 120s for 2m (the actionable
  one; the API can look healthy while this fires).
- **WorkerDown** — `up{job="worker"} == 0` for 1m.
- **APIErrorRateHigh** — 5xx ratio > 5% over 5m.

Locally Grafana is at `http://localhost:3000` (admin/your password). On the
deployment it is bound to `127.0.0.1` and reachable **only through an SSH
tunnel** — see [RUNBOOK.md](RUNBOOK.md#accessing-grafana-on-the-deployment).
Logs are structured JSON on stdout, correlatable by `request_id`.

## Backup and restore

The `backup` service dumps Postgres every `BACKUP_INTERVAL` (default hourly),
verifies each archive is readable, gzips it, and prunes dumps older than 7 days;
files land in `./backups` as `dropme_<UTC>_<sha>.dump.gz`.

Restores are non-destructive by default. `make restore` restores the newest dump
into a scratch database, and `make verify-restore` compares it to the source by
row count, `created_at` range, and an md5 over the ordered `id` list, printing
**PASS/FAIL**. The live-database path is gated behind a typed confirmation. Full
procedures in [RUNBOOK.md#backup](RUNBOOK.md#backup) and
[RUNBOOK.md#restore](RUNBOOK.md#restore). A verified restore transcript is in
`evidence/06-backup/restore-test.log`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make migrate`/API can't reach Postgres — "connection refused" to localhost | A leftover exported `DATABASE_URL`/`PG*` in your shell; Compose gives exported vars precedence over `.env` | `unset DATABASE_URL POSTGRES_PASSWORD …` (or use a clean shell), then re-run |
| `pytest` prints ~28 connection errors | Tests need Postgres+Redis on `localhost` with the conftest credentials | Start the two `test-pg`/`test-redis` containers (see Running tests) |
| A container is `unhealthy` while it clearly serves | busybox `wget` resolves `localhost` → `::1`, but the service listens on IPv4 | Use `127.0.0.1` in the healthcheck (already done for the frontend) |
| `password authentication failed for user "…"` after changing a password | A stale `pgdata` volume keeps the old password (init vars apply only on first boot) | `docker compose down -v` to reset (destroys local data), then `make up` |
| `curl http://localhost` right after starting → connection refused | `docker compose up -d` returns before containers are healthy | Use `make up` (it adds `--wait`); Caddy is healthy seconds later |
| Worker fails to start with `Duplicated timeseries in CollectorRegistry` | Ran `python -m dropme.worker`, which imports the module twice | Run via the `dropme-worker` entry point (compose already does) |
| `WorkerDown` / `EventProcessingLag` firing | Worker down or backlog growing | Follow [RUNBOOK.md#worker-down](RUNBOOK.md#worker-down) / [#event-processing-lag](RUNBOOK.md#event-processing-lag) — check `up{job="worker"}` first |
| Can't reach Grafana on the EC2 host | It is bound to `127.0.0.1`, not exposed | Use the SSH tunnel: `ssh -L 3000:127.0.0.1:3000 ubuntu@<eip>` |

## Shutting down

```bash
make down            # docker compose down --remove-orphans
```

The worker has a 30s stop grace period and RQ shuts down warm, finishing its
in-flight job. Add `-v` only to delete the data volumes. On EC2, stop the stack
with `docker compose -f docker-compose.yml -f docker-compose.deploy.yml down`
(volumes persist), or tear down the instance entirely with `terraform destroy`.
See [RUNBOOK.md#safe-shutdown](RUNBOOK.md#safe-shutdown).

## Known limitations

The intentional trade-offs, accepted risks, and next steps are documented in
[ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md) and
[SECURITY.md](SECURITY.md). Highlights: single-host deployment (no HA), the app
connects to Postgres as a superuser, a single shared API key, backups have
RPO = one interval with no PITR, and rollback is source-based rather than by
immutable release tag.
