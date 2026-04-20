"""Résolution de chemins indépendante du cwd (utile en mode PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.templating import Jinja2Templates

PACKAGE_DIR: Path = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):
    # PyInstaller extrait les données dans sys._MEIPASS.
    BUNDLE_DIR: Path = Path(getattr(sys, "_MEIPASS", PACKAGE_DIR.parent))
    TEMPLATES_DIR: Path = BUNDLE_DIR / "app" / "templates"
    STATIC_DIR: Path = BUNDLE_DIR / "app" / "static"
else:
    TEMPLATES_DIR = PACKAGE_DIR / "templates"
    STATIC_DIR = PACKAGE_DIR / "static"

# Instance Jinja2 partagée par tous les routeurs.
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
