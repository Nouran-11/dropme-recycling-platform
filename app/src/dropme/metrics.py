import time
from collections.abc import Iterator

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import text

from dropme.config import get_settings
from dropme.db import engine
from dropme.queue import event_queue, redis_conn

_settings = get_settings()

http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests handled by the API",
    ["method", "route", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
)

events_created_total = Counter(
    "dropme_events_created_total",
    "Events accepted at the API, by material type",
    ["material_type"],
)

_build_info = Gauge(
    "dropme_build_info",
    "Build identity of the running API (always 1)",
    ["version", "git_sha"],
)
_build_info.labels(version=_settings.version, git_sha=_settings.git_sha).set(1)

_ALL_STATUSES = ("received", "processing", "processed", "failed")
_DB_CACHE_TTL_SECONDS = 10.0


class DropmeCollector(Collector):
    """Scrape-time gauges derived from Postgres and Redis.

    The Postgres-derived values are cached for 10s so a tight scrape interval
    cannot turn every scrape into two aggregate queries against the events table.
    """

    def __init__(self) -> None:
        self._cache_at = 0.0
        self._db: dict | None = None

    def _db_snapshot(self) -> dict:
        now = time.monotonic()
        if self._db is not None and now - self._cache_at < _DB_CACHE_TTL_SECONDS:
            return self._db

        counts: dict[str, int] = {}
        oldest_age = 0.0
        postgres_up = 1
        try:
            with engine.connect() as conn:
                for status, count in conn.execute(
                    text("SELECT status, count(*) FROM events GROUP BY status")
                ):
                    counts[str(status)] = int(count)
                oldest_age = float(
                    conn.execute(
                        text(
                            "SELECT COALESCE(EXTRACT(EPOCH FROM now() - MIN(created_at)), 0) "
                            "FROM events WHERE status IN ('received', 'processing')"
                        )
                    ).scalar_one()
                )
        except Exception:
            postgres_up = 0

        self._db = {"counts": counts, "oldest_age": oldest_age, "postgres_up": postgres_up}
        self._cache_at = now
        return self._db

    def collect(self) -> Iterator:
        snap = self._db_snapshot()

        by_status = GaugeMetricFamily(
            "dropme_events_by_status", "Current event count by status", labels=["status"]
        )
        for status in _ALL_STATUSES:
            by_status.add_metric([status], snap["counts"].get(status, 0))
        yield by_status

        oldest = GaugeMetricFamily(
            "dropme_oldest_unprocessed_event_age_seconds",
            "Age of the oldest event still in received/processing",
        )
        oldest.add_metric([], snap["oldest_age"])
        yield oldest

        depth = GaugeMetricFamily(
            "dropme_queue_depth", "Jobs waiting in the RQ queue", labels=["queue"]
        )
        try:
            depth.add_metric([event_queue.name], event_queue.count)
        except Exception:
            depth.add_metric([event_queue.name], float("nan"))
        yield depth

        dependency_up = GaugeMetricFamily(
            "dropme_dependency_up", "1 if the dependency is reachable", labels=["dependency"]
        )
        dependency_up.add_metric(["postgres"], snap["postgres_up"])
        redis_up = 1
        try:
            redis_conn.ping()
        except Exception:
            redis_up = 0
        dependency_up.add_metric(["redis"], redis_up)
        yield dependency_up


_collector_registered = False


def register_collectors() -> None:
    global _collector_registered
    if not _collector_registered:
        REGISTRY.register(DropmeCollector())
        _collector_registered = True
