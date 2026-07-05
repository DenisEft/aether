"""extend_process_runtime_context

Revision ID: 3b84b68faca0
Revises: b725e5bb88e9
Create Date: 2026-07-05 12:56:05.415588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3b84b68faca0'
down_revision: Union[str, Sequence[str], None] = 'b725e5bb88e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add context, source tracking to process_instances and comment to transitions."""
    op.add_column('process_instances', sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column('process_instances', sa.Column('source_system', sa.String(length=50), nullable=True))
    op.add_column('process_instances', sa.Column('source_record_id', sa.String(length=255), nullable=True))
    op.add_column('process_transitions', sa.Column('comment', sa.Text(), nullable=True))
    op.add_column('process_transitions', sa.Column('field_changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Remove added columns."""
    op.drop_column('process_transitions', 'field_changes')
    op.drop_column('process_transitions', 'comment')
    op.drop_column('process_instances', 'source_record_id')
    op.drop_column('process_instances', 'source_system')
    op.drop_column('process_instances', 'context')
