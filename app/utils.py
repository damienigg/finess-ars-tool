"""Petites utilités transverses."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Horodatage UTC, naïf (compatible colonnes `DateTime` sans tz).

    Remplace ``datetime.utcnow()`` déprécié en Python 3.12+.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
