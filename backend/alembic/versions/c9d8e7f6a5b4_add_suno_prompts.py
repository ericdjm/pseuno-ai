"""add suno_prompts table

Revision ID: c9d8e7f6a5b4
Revises: b8c6e7d2f1a9
Create Date: 2025-02-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c9d8e7f6a5b4"
down_revision = "b8c6e7d2f1a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suno_prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Core prompt content
        sa.Column("suno_prompt", sa.Text(), nullable=False),
        sa.Column("exclude", sa.Text(), nullable=False, server_default=""),
        sa.Column("weirdness", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("style_influence", sa.Integer(), nullable=False, server_default="50"),
        # UX fields
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Shareability fields
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=False,
            server_default="private",
        ),
        sa.Column("share_id", sa.String(length=24), nullable=False, unique=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_suno_prompts_owner_user_id", "suno_prompts", ["owner_user_id"]
    )
    op.create_index("ix_suno_prompts_share_id", "suno_prompts", ["share_id"])


def downgrade() -> None:
    op.drop_index("ix_suno_prompts_share_id", table_name="suno_prompts")
    op.drop_index("ix_suno_prompts_owner_user_id", table_name="suno_prompts")
    op.drop_table("suno_prompts")

