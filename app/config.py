"""Configuration applicative chargée depuis l'environnement."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


APP_DIR_NAME = "Finess-for-Laure"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _user_data_dir() -> Path:
    """Dossier de données utilisateur par OS (utilisé en mode packagé)."""
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.getenv("XDG_DATA_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    return base / APP_DIR_NAME


def _default_database_url() -> str:
    # En mode packagé (PyInstaller pose sys.frozen), on stocke la base dans
    # le dossier de données de l'utilisateur pour qu'elle survive aux mises à jour.
    if getattr(sys, "frozen", False):
        data_dir = _user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir / 'finess.db'}"
    return "sqlite:///./finess.db"


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_level: str
    log_file: Optional[str]
    max_upload_mb: int
    environment: str
    sirene_api_base: str
    sirene_api_token: Optional[str]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def _default_log_file() -> Optional[str]:
    if getattr(sys, "frozen", False):
        data_dir = _user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / "app.log")
    return None


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL") or _default_database_url(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_file=os.getenv("LOG_FILE") or _default_log_file(),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 100),
        environment=os.getenv("APP_ENV", "development"),
        sirene_api_base=os.getenv(
            "SIRENE_API_BASE",
            "https://api.insee.fr/entreprises/sirene/V3.11",
        ),
        sirene_api_token=os.getenv("SIRENE_API_TOKEN") or None,
    )


settings = load_settings()
