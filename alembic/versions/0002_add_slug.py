"""Add slug column to videos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-28
"""

import secrets

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Minimal table reference for bulk backfill — self-contained, no app import.
_videos = sa.table("videos", sa.column("id", sa.Integer()), sa.column("slug", sa.String()))


def _generate_slug() -> str:
    return secrets.token_urlsafe(8)


def upgrade() -> None:
    # 1. Add nullable column first (SQLite can't add non-null without a default).
    op.add_column("videos", sa.Column("slug", sa.String(16), nullable=True))

    # 2. Backfill existing rows.
    conn = op.get_bind()
    rows = conn.execute(sa.select(_videos.c.id).where(_videos.c.slug == None))  # noqa: E711
    for (row_id,) in rows:
        conn.execute(sa.update(_videos).where(_videos.c.id == row_id).values(slug=_generate_slug()))

    # 3. Tighten: make non-null and add unique index (batch mode required for SQLite).
    with op.batch_alter_table("videos") as batch_op:
        batch_op.alter_column("slug", nullable=False)
        batch_op.create_index("ix_videos_slug", ["slug"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_index("ix_videos_slug")
        batch_op.drop_column("slug")
