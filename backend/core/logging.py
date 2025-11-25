import logging
from logging.config import dictConfig
from typing import Literal

try:
    # Optional dependency used in production for structured logs.
    from pythonjsonlogger import jsonlogger  # type: ignore  # noqa: F401

    JSON_FORMATTER_CLASS = "pythonjsonlogger.jsonlogger.JsonFormatter"
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    JSON_FORMATTER_CLASS = None

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


def configure_logging(level: LogLevel = "INFO") -> None:
    """Configure structured logging across the app."""
    formatters = {
        "default": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }
    }
    if JSON_FORMATTER_CLASS:
        formatters["json"] = {
            "class": JSON_FORMATTER_CLASS,
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if JSON_FORMATTER_CLASS else "default",
                }
            },
            "root": {"handlers": ["console"], "level": level.upper()},
        }
    )

    logging.getLogger("uvicorn").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
    logging.getLogger("uvicorn.access").handlers = []
