"""add lyrics column to suno_prompts

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-01-09 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lyrics column (default empty string for existing prompts)
    op.add_column(
        "suno_prompts",
        sa.Column("lyrics", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("suno_prompts", "lyrics")
