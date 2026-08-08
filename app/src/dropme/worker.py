from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import redis
import structlog
from rq import Worker
from rq.job import get_current_job

from dropme.config import get_settings
from dropme.db import SessionLocal
from dropme.logging import configure_logging
from dropme.models import Event, EventStatus, MaterialType
from dropme.queue import event_queue, redis_conn

logger = structlog.get_logger()

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

        try:
            event.status = EventStatus.processing
            session.commit()

            weight = GRAMS_PER_ITEM[event.material_type] * event.item_count
            event.estimated_weight_g = weight
            event.status = EventStatus.processed
            event.processed_at = datetime.now(timezone.utc)
            event.failure_reason = None
            session.commit()
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
            log.error("processing_failed", error=str(exc))
            raise


class HeartbeatWorker(Worker):
    def heartbeat(self, timeout: int | None = None, pipeline=None) -> None:
        super().heartbeat(timeout, pipeline)
        try:
            self.connection.set(
                "worker:heartbeat", datetime.now(timezone.utc).isoformat(), ex=60
            )
        except redis.exceptions.RedisError:
            self.log.warning("failed to write worker:heartbeat")


def main() -> None:
    configure_logging(get_settings().log_level)
    worker = HeartbeatWorker([event_queue], connection=redis_conn)
    worker.worker_ttl = WORKER_TTL_SECONDS
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
