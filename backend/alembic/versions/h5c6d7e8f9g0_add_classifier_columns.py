"""Add classifier columns to suno_prompts

Revision ID: h5c6d7e8f9g0
Revises: fc77c50fc50b
Create Date: 2026-01-18

Adds columns for caching style classifier results:
- classifier_traits: JSON dict of trait weights
- classifier_bank_sims: JSON dict of bank similarity scores
- classifier_prompt_hash: SHA-256 hash for staleness detection
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h5c6d7e8f9g0"
down_revision = "fc77c50fc50b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add classifier columns to suno_prompts
    op.add_column(
        "suno_prompts",
        sa.Column("classifier_traits", sa.Text(), nullable=True),
    )
    op.add_column(
        "suno_prompts",
        sa.Column("classifier_bank_sims", sa.Text(), nullable=True),
    )
    op.add_column(
        "suno_prompts",
        sa.Column("classifier_prompt_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suno_prompts", "classifier_prompt_hash")
    op.drop_column("suno_prompts", "classifier_bank_sims")
    op.drop_column("suno_prompts", "classifier_traits")
