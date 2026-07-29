"""make answer_files.qwen_file_id nullable

Revision ID: 4efa7a5138d8
Revises: 9ad61fd9568d
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4efa7a5138d8'
down_revision: Union[str, Sequence[str], None] = '9ad61fd9568d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('answer_files') as batch_op:
        batch_op.alter_column(
            'qwen_file_id',
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('answer_files') as batch_op:
        batch_op.alter_column(
            'qwen_file_id',
            existing_type=sa.String(length=255),
            nullable=False,
        )
