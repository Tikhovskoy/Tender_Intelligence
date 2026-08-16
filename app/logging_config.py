"""Настройка структурированного журналирования."""

import logging
import sys

import structlog


def configure_logging(log_level: str) -> None:
    """Настроить JSON-логи без вывода конфиденциальных значений."""
    level = getattr(logging, log_level)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
