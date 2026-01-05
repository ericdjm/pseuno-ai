"""add genres and user_genres

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2025-02-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("normalized_name", name="uq_genres_normalized_name"),
    )
    op.create_index("ix_genres_normalized_name", "genres", ["normalized_name"])

    op.create_table(
        "user_genres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "genre_id",
            sa.Integer(),
            sa.ForeignKey("genres.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "genre_id", name="uq_user_genres_user_genre"
        ),
    )
    op.create_index("ix_user_genres_user_id", "user_genres", ["user_id"])
    op.create_index("ix_user_genres_genre_id", "user_genres", ["genre_id"])

    genres_table = sa.table(
        "genres",
        sa.column("name", sa.String),
        sa.column("normalized_name", sa.String),
    )

    seed_genres = [
        "ambient",
        "art pop",
        "dream pop",
        "electronic",
        "folk",
        "funk",
        "hip-hop",
        "house",
        "industrial",
        "indie rock",
        "jazz fusion",
        "lo-fi",
        "neo-soul",
        "post-punk",
        "progressive rock",
        "psychedelic",
        "R&B",
        "shoegaze",
        "synth-pop",
        "trip-hop",
    ]
    op.bulk_insert(
        genres_table,
        [
            {"name": genre, "normalized_name": genre.strip().lower()}
            for genre in seed_genres
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_user_genres_genre_id", table_name="user_genres")
    op.drop_index("ix_user_genres_user_id", table_name="user_genres")
    op.drop_table("user_genres")
    op.drop_index("ix_genres_normalized_name", table_name="genres")
    op.drop_table("genres")
