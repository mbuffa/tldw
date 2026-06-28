import os
import pathlib

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tldw.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Repo root — used to locate alembic.ini regardless of the working directory.
_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Apply all pending Alembic migrations to the database."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(_BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BASE_DIR / "alembic"))
    command.upgrade(cfg, "head")
