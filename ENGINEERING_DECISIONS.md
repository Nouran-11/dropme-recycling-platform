# Engineering decisions

## What did I prioritize first, and why?

I followed the order in the brief: working application, reproducible local
environment, tests and CI, then observability, recovery, and security. The
reasoning was that everything downstream depends on the baseline. There is no
point writing alert rules against metrics from an app that doesn't run, and no
point building a backup script before there is a schema worth backing up.

I also wanted a submittable state as early as possible. By the time the
containerised stack came up twice from a clean cache, I had something I could
have handed in. Everything after that was upside rather than risk.

The one place I deviated: I spent longer on observability than planned, because
the brief's scenario — "events reach the API but stay unprocessed" — is a lag
problem, and I wanted the metric, the alert, the dashboard, and the failure
drill to be one coherent story rather than four separate checkboxes.

I also deferred the release pipeline until after recovery and deployment were
done, then came back and built it. That ordering was deliberate: a verified
restore and a real failure drill were worth more than release tagging if I ran
out of time. I didn't, so both exist.

## What did I intentionally leave incomplete?

**Deploying from the registry.** The release pipeline builds, scans, and pushes
tagged images to GHCR, but the EC2 instance still builds from source rather than
pulling `v1.0.0`. `/version` there reports the real git SHA, so the running
version is identifiable, but rollback means checking out a previous commit and
rebuilding rather than redeploying an immutable tag. Closing that is a user_data
change and a `docker compose pull`, not new infrastructure.

**A second failure scenario.** I ran the worker-crash drill only. A Postgres
outage would show a different signature — `/ready` returning 503, writes
failing — and contrasting the two would have been stronger, but one drill done
properly beat two done shallowly.

**A least-privilege database role.** The application connects as the Postgres
superuser created by the image. It works, but it grants far more than the app
needs.

## What is the largest remaining risk?

The gap between committing an event and enqueuing its job. `POST /events`
commits the row, then enqueues; if Redis is unavailable at that moment the event
is durably stored but no job exists, and nothing retries it. It sits at
`received` forever.

I chose this ordering deliberately — enqueuing first would let the worker
dequeue an event whose commit later failed, and a queue outage should not fail a
durable write. I wrapped the enqueue so the failure is logged and the API still
returns 201. But the event is only *visible* through the processing-lag metric;
it is never automatically recovered. A transactional outbox, or a reconciliation
sweep that re-enqueues anything stuck in `received` beyond a threshold, would
close it. Both were out of scope at this size.

## Which decision involved the biggest trade-off?

Switching the worker from RQ's default `Worker` to `SimpleWorker`.

I found the problem by measurement, not by reading: `dropme_jobs_processed_total`
sat at zero no matter how many events processed. The cause is that the default
worker forks a child process per job, so the counter increments in the child's
copy-on-write memory and dies with it, while the metrics server in the parent
serves an untouched registry.

Three options. `prometheus_client`'s multiprocess mode keeps the fork but needs a
shared writable directory, dead-PID cleanup, and has gauge-mode caveats. Pushing
to a Pushgateway from the child adds infrastructure and is semantically wrong for
liveness in a scrape model. `SimpleWorker` runs jobs in-process, so the counters
live where the server reads them, with no extra moving parts.

I took `SimpleWorker` and accepted the cost: no per-job crash isolation. Normal
exceptions behave identically either way, but a process-fatal event — a segfault
in a C extension, an OOM kill, a hang needing SIGKILL — now takes the whole
worker down instead of one child. I judged that acceptable because the job is
pure Python, short-lived, and opens a fresh session each time, and because the
container restarts automatically. At higher volume, or with native code in the
job, I would revisit it and pay the complexity of multiprocess mode.

## What would I do during the next three working days?

**Day 1 — deploy from the registry.** Change user_data to pull the tagged image
from GHCR instead of building on the instance, so deployment is a pull rather
than a five-minute build and rollback is redeploying a previous tag. Add a
staging environment so a release is exercised somewhere before production.

**Day 2 — harden the data path.** A least-privilege database role owning only
what it needs. WAL archiving with pgBackRest or wal-g so the recovery point
objective drops from one backup interval to seconds, with dumps in versioned
object storage rather than a volume on one host. A reconciliation job for events
stranded by a failed enqueue.

**Day 3 — production-shaped operations.** Two worker replicas so a single
failure degrades throughput instead of halting it. Per-machine credentials
instead of one shared API key, with rotation and per-device revocation. A second
failure drill against Postgres, and a load test to find where a single
`m7i-flex.large` actually saturates.