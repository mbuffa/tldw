import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tldw.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import Video, generate_slug  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Migrate existing databases that predate the slug column.
    col_names = {c["name"] for c in inspect(engine).get_columns("videos")}
    if "slug" not in col_names:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE videos ADD COLUMN slug VARCHAR(16)"))
            conn.commit()

        # Backfill slugs for existing rows.
        db = SessionLocal()
        try:
            for video in db.query(Video).filter(Video.slug == None).all():  # noqa: E711
                video.slug = generate_slug()
            db.commit()
        finally:
            db.close()

        with engine.connect() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_videos_slug ON videos(slug)"
                )
            )
            conn.commit()
