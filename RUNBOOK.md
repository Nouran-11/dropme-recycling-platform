# Runbook

Operational procedures for the Drop Me platform. The first three sections are
linked directly from alert annotations, so their headings must not be renamed
(the anchors `#event-processing-lag`, `#worker-down`, `#api-errors` are load-
bearing). Commands assume you are in the repo root with the stack running; on
EC2, `cd /opt/dropme` first and add `-f docker-compose.deploy.yml` to compose
commands.

## Event processing lag

Fired by the `EventProcessingLag` alert:
`dropme_oldest_unprocessed_event_age_seconds > 120` for 2 minutes.

**Symptom.** Events are accepted (`POST /events` still returns 201) but are not
being processed — the oldest event stuck in `received`/`processing` keeps
getting older. Writes look healthy; the backlog grows silently.

**Check first — in this order (the diagnosis path from the failure drill):**
1. `up{job="worker"}` in Prometheus, or dashboard row 1. If it is `0`, the
   worker is down — go to [Worker down](#worker-down); that is the usual cause.
2. `dropme_queue_depth` (dashboard row 3). Climbing depth with the worker *up*
   means the worker is running but not keeping pace or is stuck on a job.
3. `docker compose logs worker` — look for the last `processed` line and whether
   a job is wedged, erroring, or retrying.

**Likely causes.**
- Worker process down or unreachable (most common — see Worker down).
- Worker alive but stuck on a slow/looping job, or throughput below arrival rate.
- Redis reachable by the API but not the worker, so jobs enqueue but never drain.
- A burst of traffic exceeding a single worker's capacity.

**Fix.**
- Worker down: restart it — `docker compose restart worker` — and watch the
  oldest-age metric fall back under 120s as the backlog drains.
- Worker stuck: `docker compose restart worker`; RQ re-runs the in-flight job
  (idempotent — only `processed` rows are skipped). Repeated failures on one
  event indicate a poison job; inspect it and consider a dead-letter queue.
- Under-capacity: scale workers (`docker compose up -d --scale worker=2`) or, in
  production, run `replicas >= 2` and autoscale on `dropme_queue_depth`.

## Worker down

Fired by the `WorkerDown` alert: `up{job="worker"} == 0` for 1 minute.

**Symptom.** Prometheus cannot scrape `worker:9100`. The API and `/ready` stay
healthy; events pile up at `received`. Typically fires ~1 minute before
[Event processing lag](#event-processing-lag) as the backlog ages.

**Check first.**
1. `docker compose ps worker` — is the container running or exited/restarting?
2. `docker compose logs --tail=50 worker` — crash traceback, OOM, or a clean
   `warm shut down`?
3. From another service, confirm reachability: the metrics endpoint should
   answer on `worker:9100/metrics`.

**Likely causes.**
- Worker container crashed or was stopped (`SimpleWorker` runs jobs in-process,
  so a process-fatal error takes the worker down — see SECURITY/decisions).
- Redis unreachable, so the worker cannot dequeue and its metrics scrape context
  is degraded.
- Host resource exhaustion (memory/CPU) killed the process.

**Fix.**
- `docker compose restart worker`; confirm `up{job="worker"}` returns to 1 and
  the `worker:heartbeat` key reappears in Redis.
- If it crash-loops, read the traceback; a poison job will fail on every retry —
  remove/repair the event and restart.
- Prevention: `replicas >= 2`, restart policy / K8s liveness probe, a
  dead-letter queue for repeatedly failing jobs.

## API errors

Fired by the `APIErrorRateHigh` alert: 5xx responses exceed 5% of requests over
5 minutes.

**Symptom.** Clients receive 5xx from the API. Unlike the two failures above,
this *is* visible at the write path.

**Check first.**
1. `GET /ready` — a 503 names the failed dependency (`postgres` or `redis`) in
   its body.
2. `dropme_dependency_up{dependency=...}` (dashboard row 1) to confirm which
   dependency is down.
3. `docker compose logs --tail=100 api` — correlate by `request_id`; look for
   DB connection errors or unhandled exceptions.

**Likely causes.**
- Postgres down, unreachable, or out of connections (pool exhausted).
- Redis down — note writes still return 201 (enqueue failure is swallowed and
  logged), so a pure-Redis outage shows as lag, not 5xx; 5xx points at Postgres.
- A code regression; correlate the onset with `dropme_build_info` /
  `GET /version` to see if it began after a specific release.

**Fix.**
- Restart the failed dependency (`docker compose restart postgres` / `redis`)
  and confirm `/ready` returns 200.
- Connection exhaustion: reduce load or add a pgbouncer layer; the API pool is
  `pool_size=5 + max_overflow=5` per process.
- Regression: roll back — see [Rollback](#rollback).

## Backup

**How it runs.** The `backup` service runs `ops/cron/backup-loop.sh`, which calls
`ops/backup.sh` every `BACKUP_INTERVAL` seconds (default 3600). Each run does
`pg_dump -Fc`, verifies the archive is readable (`pg_restore --list`), gzips it,
and checks gzip integrity. A failed run logs and the loop continues.

**Where dumps land.** The host `./backups` directory (bind-mounted into the
service), named `dropme_<UTC-timestamp>_<git-sha>.dump.gz`. `backups/` and
`*.dump` are gitignored.

**Retention.** Dumps older than 7 days are deleted on each run.

**Manual backup.** `make backup` (runs `backup.sh` once inside the service).

**Production note.** Local dumps to a volume have RPO = one backup interval and
no PITR. Production would use managed snapshots + versioned object storage and
WAL archiving.

## Restore

Restores are non-destructive by default.

**Verify a backup (scratch).** `make restore` restores the newest dump into a
throwaway database `dropme_restore_test`; `make verify-restore` compares the
source and restored databases by row count, `min`/`max(created_at)`, and an md5
over the ordered `id` list, printing PASS or FAIL. Neither touches production.

**Restore into production.** Only when you actually need to recover live data:
```
docker compose exec backup bash /ops/restore.sh --target production
```
It prints a warning and requires you to type the database name (`dropme`) to
confirm; any mismatch aborts. It restores with `--clean --if-exists`. Stop
writers first (`docker compose stop api worker`), restore, then start them again.

## Rollback

There is no image registry or release tag, so rollback is by source, not tag:

```
ssh ubuntu@<eip>
cd /opt/dropme
git log --oneline            # find the previous good commit
git checkout <previous-sha>
docker compose -f docker-compose.yml -f docker-compose.deploy.yml up -d --build --wait
curl -s https://<eip>.sslip.io/api/version   # confirm git_sha flipped back
```

Because `/version` and `dropme_build_info` carry the git SHA, you can confirm
exactly which build is running before and after. (A registry with `sha`/`vX.Y.Z`
tags would make this atomic — noted as future work.)

## Safe shutdown

**Local.** `make down` (`docker compose down --remove-orphans`). The worker has
`stop_grace_period: 30s` and RQ performs a warm shutdown, finishing its current
job before exiting. Add `-v` only if you intend to delete the data volumes.

**On EC2.** Stop the stack without destroying data:
```
ssh ubuntu@<eip>
cd /opt/dropme
docker compose -f docker-compose.yml -f docker-compose.deploy.yml down
```
Named volumes (Postgres, Grafana, Prometheus, Caddy certs) persist. To tear down
the whole instance and its resources, run `terraform destroy` from
`deploy/terraform/`.

## Accessing Grafana on the deployment

Grafana is bound to `127.0.0.1:3000` on the instance and is never exposed to the
internet (the security group opens only 80/443/22). Reach it through an SSH
tunnel:

```
ssh -L 3000:127.0.0.1:3000 ubuntu@<eip>
# then open http://localhost:3000 in your browser
```

Log in as `admin`; the password is `GF_SECURITY_ADMIN_PASSWORD` in
`/opt/dropme/.env` on the instance (generated by `openssl rand`, so read it there
rather than guessing).
