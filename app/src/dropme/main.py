import secrets
import uuid
from uuid import UUID

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from dropme.config import get_settings
from dropme.db import engine, get_session
from dropme.logging import configure_logging
from dropme.models import Event, EventStatus
from dropme.queue import enqueue_process_event, redis_conn
from dropme.schemas import EventCreate, EventOut

configure_logging(get_settings().log_level)
logger = structlog.get_logger()

app = FastAPI(title="Drop Me Recycling API")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    # Method and path only — never the body or headers, which carry the API key.
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )
    return response


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


@app.post(
    "/events",
    status_code=201,
    response_model=EventOut,
    dependencies=[Depends(require_api_key)],
)
def create_event(
    payload: EventCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> Event:
    event = Event(
        machine_id=payload.machine_id,
        material_type=payload.material_type,
        item_count=payload.item_count,
        event_timestamp=payload.event_timestamp,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    # Enqueue only after the row is durably committed: enqueuing first risks the
    # worker dequeuing an event_id whose commit later failed. A queue outage must
    # not fail the write — the event is safely persisted as 'received' and will
    # surface via the oldest-unprocessed-age metric for the worker to reconcile.
    try:
        enqueue_process_event(event.id)
    except Exception as exc:
        logger.error("enqueue_failed", event_id=str(event.id), error=str(exc))

    response.headers["Location"] = f"/events/{event.id}"
    return event


@app.get("/events", response_model=list[EventOut])
def list_events(
    status: EventStatus | None = None,
    machine_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[Event]:
    stmt = select(Event)
    if status is not None:
        stmt = stmt.where(Event.status == status)
    if machine_id is not None:
        stmt = stmt.where(Event.machine_id == machine_id)
    stmt = stmt.order_by(Event.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, session: Session = Depends(get_session)) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> Response:
    failed: list[str] = []
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        failed.append("postgres")
    try:
        redis_conn.ping()
    except Exception:
        failed.append("redis")

    if failed:
        return JSONResponse(
            status_code=503, content={"status": "not ready", "failed": failed}
        )
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/version")
def version() -> dict[str, str]:
    s = get_settings()
    return {"version": s.version, "git_sha": s.git_sha, "built_at": s.built_at}
