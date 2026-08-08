from uuid import UUID

import redis
from rq import Queue

from dropme.config import get_settings

_settings = get_settings()

redis_conn = redis.Redis.from_url(_settings.redis_url)
event_queue = Queue("events", connection=redis_conn)


def enqueue_process_event(event_id: UUID) -> str:
    # Enqueue by dotted path so the API process never imports the worker module
    # (and its heavier deps). Retry policy is added with the worker in item 6.
    job = event_queue.enqueue("dropme.worker.process_event", str(event_id))
    return job.id
