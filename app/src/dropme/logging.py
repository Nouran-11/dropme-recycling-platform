import logging

import structlog

# Redacted by key name so a sensitive value can never reach stdout even if some
# call site passes it by mistake. request bodies are handled by simply never
# logging them.
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "x_api_key",
        "x-api-key",
        "authorization",
        "database_url",
        "redis_url",
        "password",
        "secret",
        "token",
    }
)
_REDACTED = "***redacted***"


def _redact_sensitive(logger: object, method_name: str, event_dict: dict) -> dict:
    for key in event_dict:
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
