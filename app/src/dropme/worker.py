import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import redis
import structlog
from prometheus_client import Counter, Histogram, start_http_server
from rq import SimpleWorker
from rq.job import get_current_job

from dropme.config import get_settings
from dropme.db import SessionLocal
from dropme.logging import configure_logging
from dropme.models import Event, EventStatus, MaterialType
from dropme.queue import event_queue, redis_conn

logger = structlog.get_logger()

WORKER_METRICS_PORT = 9100

jobs_processed_total = Counter(
    "dropme_jobs_processed_total", "Events processed to completion by the worker"
)
jobs_failed_total = Counter("dropme_jobs_failed_total", "Jobs that raised and were marked failed")
job_duration_seconds = Histogram(
    "dropme_job_duration_seconds", "Wall-clock duration of process_event"
)

# Rough per-material average masses (grams per returned item). These are
# estimates for demonstration, not calibrated scale readings.
GRAMS_PER_ITEM: dict[MaterialType, Decimal] = {
    MaterialType.PET: Decimal("18"),
    MaterialType.ALU: Decimal("15"),
    MaterialType.GLASS: Decimal("300"),
    MaterialType.HDPE: Decimal("40"),
    MaterialType.OTHER: Decimal("25"),
}

# Keep the worker's dequeue loop cycling well inside the heartbeat key's 60s TTL
# so an idle (but alive) worker never looks dead. dequeue_timeout = ttl - 15.
WORKER_TTL_SECONDS = 45


def process_event(event_id: str) -> None:
    job = get_current_job()
    log = logger.bind(event_id=event_id, job_id=job.id if job else None)

    with SessionLocal() as session:
        event = session.get(Event, UUID(event_id))
        if event is None:
            log.error("event_not_found")
            raise ValueError(f"event {event_id} not found")

        if event.status == EventStatus.processed:
            log.info("already_processed_skipping")
            return

        start = time.perf_counter()
        try:
            event.status = EventStatus.processing
            session.commit()

            weight = GRAMS_PER_ITEM[event.material_type] * event.item_count
            event.estimated_weight_g = weight
            event.status = EventStatus.processed
            event.processed_at = datetime.now(UTC)
            event.failure_reason = None
            session.commit()
            job_duration_seconds.observe(time.perf_counter() - start)
            jobs_processed_total.inc()
            log.info("processed", estimated_weight_g=str(weight))
        except Exception as exc:
            # Record the failure durably, then re-raise so RQ marks the job
            # failed and applies the retry policy.
            session.rollback()
            failed = session.get(Event, UUID(event_id))
            if failed is not None:
                failed.status = EventStatus.failed
                failed.failure_reason = str(exc)[:500]
                session.commit()
            job_duration_seconds.observe(time.perf_counter() - start)
            jobs_failed_total.inc()
            log.error("processing_failed", error=str(exc))
            raise


# SimpleWorker runs jobs in-process (no fork), so prometheus counters
# incremented in process_event live in the same process as the metrics server.
class HeartbeatWorker(SimpleWorker):
    def heartbeat(self, timeout: int | None = None, pipeline=None) -> None:
        super().heartbeat(timeout, pipeline)
        try:
            self.connection.set("worker:heartbeat", datetime.now(UTC).isoformat(), ex=60)
        except redis.exceptions.RedisError:
            self.log.warning("failed to write worker:heartbeat")


def main() -> None:
    # Run via the `dropme-worker` entry point, never `python -m dropme.worker`:
    # the latter imports this module twice (as __main__ and again when RQ loads
    # the job callable), which double-registers the metrics below.
    configure_logging(get_settings().log_level)
    start_http_server(WORKER_METRICS_PORT)
    worker = HeartbeatWorker([event_queue], connection=redis_conn)
    worker.worker_ttl = WORKER_TTL_SECONDS
    worker.work(with_scheduler=True)
