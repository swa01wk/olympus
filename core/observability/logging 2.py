from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from core.config.settings import OlympusSettings, get_settings
from core.observability.correlation import get_correlation_id

_configured = False


def _add_service_context(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    event_dict.setdefault("service", settings.service_name)
    event_dict.setdefault("env", settings.olympus_env)
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict.setdefault("correlation_id", correlation_id)
    return event_dict


def configure_logging(settings: OlympusSettings | None = None) -> None:
    global _configured
    if _configured:
        return
    if settings is not None:
        get_settings.cache_clear()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_service_context,  # type: ignore[list-item]
            timestamper,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    configure_logging()
    return structlog.get_logger(name)
