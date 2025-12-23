"""add device_token and is_guest to users

Revision ID: d1e2f3a4b5c6
Revises: c9d8e7f6a5b4, 46365e54cf44
Create Date: 2025-02-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = ("c9d8e7f6a5b4", "46365e54cf44")  # Merge heads
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add device_token column (nullable, unique)
    op.add_column(
        "users",
        sa.Column("device_token", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_users_device_token", "users", ["device_token"], unique=True)

    # Add is_guest column with default True
    # Existing users (from Spotify OAuth) should be marked as non-guests
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Update existing users to is_guest=False (they came from Spotify OAuth)
    op.execute("UPDATE users SET is_guest = false WHERE id IN (SELECT user_id FROM external_accounts)")


def downgrade() -> None:
    op.drop_index("ix_users_device_token", table_name="users")
    op.drop_column("users", "device_token")
    op.drop_column("users", "is_guest")

