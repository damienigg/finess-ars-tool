"""Configuration du logging applicatif."""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from app.config import settings


_CONFIGURED = False


def configure_logging() -> None:
    """Installe les handlers une seule fois par processus."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(settings.log_level)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)

    if settings.log_file:
        path = Path(settings.log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        rotating.setFormatter(fmt)
        root.addHandler(rotating)

    # Tame overly-chatty libraries.
    for noisy in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if settings.log_level == "INFO" else settings.log_level
        )

    _CONFIGURED = True
