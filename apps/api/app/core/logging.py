import logging

import structlog

from app.config import settings


def setup_logging() -> None:
    is_dev = settings.env == "dev"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if is_dev
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if is_dev else logging.INFO
        ),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
