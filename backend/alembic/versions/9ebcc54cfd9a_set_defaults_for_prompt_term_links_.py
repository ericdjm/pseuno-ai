"""set defaults for prompt_term_links intent/role

Revision ID: 9ebcc54cfd9a
Revises: f4abd6464545
Create Date: 2025-12-24 17:30:46.495652

"""

from alembic import op


revision = "9ebcc54cfd9a"
down_revision = "f4abd6464545"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill existing rows (defensive: should be none on fresh DBs)
    op.execute(
        "UPDATE prompt_term_links SET intent='coherent' WHERE intent IS NULL OR intent=''"
    )
    op.execute(
        "UPDATE prompt_term_links SET role='primary' WHERE role IS NULL OR role=''"
    )

    # Set DB-level defaults so raw inserts don't fail
    op.execute(
        "ALTER TABLE prompt_term_links ALTER COLUMN intent SET DEFAULT 'coherent'"
    )
    op.execute("ALTER TABLE prompt_term_links ALTER COLUMN role SET DEFAULT 'primary'")


def downgrade() -> None:
    op.execute("ALTER TABLE prompt_term_links ALTER COLUMN intent DROP DEFAULT")
    op.execute("ALTER TABLE prompt_term_links ALTER COLUMN role DROP DEFAULT")
