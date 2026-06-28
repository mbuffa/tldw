"""Initial schema.

Revision ID: 0001
Revises: —
Create Date: 2026-06-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("video_id", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("caveman", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_id", "videos", ["id"], unique=False)
    op.create_index("ix_videos_video_id", "videos", ["video_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_videos_video_id", table_name="videos")
    op.drop_index("ix_videos_id", table_name="videos")
    op.drop_table("videos")
