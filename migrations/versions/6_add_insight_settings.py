"""add_insight_settings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'insight_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('tab', sa.String(32), nullable=False),
        sa.Column('generation_frequency', sa.String(64), nullable=False, server_default='weekly_monday_8'),
        sa.Column('data_horizon', sa.String(64), nullable=False, server_default='last_2_weeks'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'tab', name='uq_insight_settings_org_tab'),
    )
    op.create_index('ix_insight_settings_org', 'insight_settings', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_insight_settings_org', table_name='insight_settings')
    op.drop_table('insight_settings')
