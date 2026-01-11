"""add_display_order_to_lyrics_threads

Revision ID: fc77c50fc50b
Revises: g4b5c6d7e8f9
Create Date: 2026-01-11 01:38:52.717490

"""

from alembic import op
import sqlalchemy as sa


revision = "fc77c50fc50b"
down_revision = "g4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add display_order column with default 0 for existing rows
    op.add_column(
        "lyrics_threads",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_lyrics_threads_display_order"),
        "lyrics_threads",
        ["display_order"],
        unique=False,
    )
    # Remove server default after adding (we'll set it in app code)
    op.alter_column("lyrics_threads", "display_order", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_lyrics_threads_display_order"), table_name="lyrics_threads")
    op.drop_column("lyrics_threads", "display_order")
