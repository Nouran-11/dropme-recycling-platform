from uuid import UUID

import redis
from rq import Queue, Retry

from dropme.config import get_settings

_settings = get_settings()

redis_conn = redis.Redis.from_url(_settings.redis_url)
event_queue = Queue("events", connection=redis_conn)


def enqueue_process_event(event_id: UUID) -> str:
    # Enqueue by dotted path so the API process never imports the worker module
    # (and its heavier deps). Backoff intervals require the worker to run with
    # its scheduler enabled (see worker.py).
    job = event_queue.enqueue(
        "dropme.worker.process_event",
        str(event_id),
        retry=Retry(max=3, interval=[5, 15, 45]),
    )
    return job.id
