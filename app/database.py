"""Connexion et session SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _build_engine(url: str) -> Engine:
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # SQLite + FastAPI: permit cross-thread usage for the shared connection pool.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, future=True)


engine: Engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crée le schéma. Utilisé en dev ou en bootstrap avant Alembic."""
    # Import models so every table is registered on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
