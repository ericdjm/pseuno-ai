"""add lyrics_threads, lyrics_checkpoints tables and parent_prompt_id to suno_prompts

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-01-09 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "g4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add parent_prompt_id and source_action to suno_prompts
    op.add_column(
        "suno_prompts",
        sa.Column("parent_prompt_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suno_prompts",
        sa.Column(
            "source_action",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_index(
        "ix_suno_prompts_parent_prompt_id",
        "suno_prompts",
        ["parent_prompt_id"],
    )
    op.create_index(
        "ix_suno_prompts_source_action",
        "suno_prompts",
        ["source_action"],
    )
    op.create_foreign_key(
        "fk_suno_prompts_parent_prompt_id",
        "suno_prompts",
        "suno_prompts",
        ["parent_prompt_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2) Create lyrics_threads table
    op.create_table(
        "lyrics_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("style_prompt_id", sa.Integer(), nullable=False),
        sa.Column("parent_thread_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("lyrics_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "source_action",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["style_prompt_id"],
            ["suno_prompts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_thread_id"],
            ["lyrics_threads.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_lyrics_threads_style_prompt_id",
        "lyrics_threads",
        ["style_prompt_id"],
    )
    op.create_index(
        "ix_lyrics_threads_parent_thread_id",
        "lyrics_threads",
        ["parent_thread_id"],
    )
    op.create_index(
        "ix_lyrics_threads_source_action",
        "lyrics_threads",
        ["source_action"],
    )

    # 3) Create lyrics_checkpoints table
    op.create_table(
        "lyrics_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("lyrics_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["lyrics_threads.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_lyrics_checkpoints_thread_id",
        "lyrics_checkpoints",
        ["thread_id"],
    )

    # 4) Backfill: create a LyricsThread for each SunoPrompt that has lyrics
    # This ensures existing prompts with lyrics have at least one song
    op.execute(
        """
        INSERT INTO lyrics_threads (style_prompt_id, title, lyrics_text, source_action, created_at, updated_at)
        SELECT id, COALESCE(title, 'Song 1'), lyrics, 'backfill_from_prompt_lyrics', created_at, updated_at
        FROM suno_prompts
        WHERE lyrics IS NOT NULL AND lyrics != ''
    """
    )


def downgrade() -> None:
    # Drop checkpoints first (FK to threads)
    op.drop_index("ix_lyrics_checkpoints_thread_id", table_name="lyrics_checkpoints")
    op.drop_table("lyrics_checkpoints")

    # Drop threads
    op.drop_index("ix_lyrics_threads_source_action", table_name="lyrics_threads")
    op.drop_index("ix_lyrics_threads_parent_thread_id", table_name="lyrics_threads")
    op.drop_index("ix_lyrics_threads_style_prompt_id", table_name="lyrics_threads")
    op.drop_table("lyrics_threads")

    # Drop suno_prompts columns
    op.drop_constraint(
        "fk_suno_prompts_parent_prompt_id", "suno_prompts", type_="foreignkey"
    )
    op.drop_index("ix_suno_prompts_source_action", table_name="suno_prompts")
    op.drop_index("ix_suno_prompts_parent_prompt_id", table_name="suno_prompts")
    op.drop_column("suno_prompts", "source_action")
    op.drop_column("suno_prompts", "parent_prompt_id")
