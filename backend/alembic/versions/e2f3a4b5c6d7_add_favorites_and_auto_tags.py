"""add is_favorite, auto_tags, generation_id to suno_prompts

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-01-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_favorite column (default False, indexed)
    # Existing rows (manually saved prompts) should be marked as favorites
    op.add_column(
        "suno_prompts",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_suno_prompts_is_favorite", "suno_prompts", ["is_favorite"])

    # Add auto_tags column (JSON-encoded list stored as Text)
    op.add_column(
        "suno_prompts",
        sa.Column("auto_tags", sa.Text(), nullable=False, server_default="[]"),
    )

    # Add generation_id column (nullable, for correlating with generation responses)
    op.add_column(
        "suno_prompts",
        sa.Column("generation_id", sa.String(length=24), nullable=True),
    )

    # Backfill: existing saved prompts become favorites (they were explicitly saved)
    op.execute("UPDATE suno_prompts SET is_favorite = true")


def downgrade() -> None:
    op.drop_index("ix_suno_prompts_is_favorite", table_name="suno_prompts")
    op.drop_column("suno_prompts", "is_favorite")
    op.drop_column("suno_prompts", "auto_tags")
    op.drop_column("suno_prompts", "generation_id")

