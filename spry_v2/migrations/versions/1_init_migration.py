"""Init migration

Revision ID: 97c0fb06b3df
Revises: 
Create Date: 2025-12-08 21:51:00.857126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '97c0fb06b3df'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =====================
# ENUM DEFINITIONS
# =====================

organization_cost_type_enum = postgresql.ENUM(
    'PER_MEMBER', 'AVERAGE',
    name='organizationcosttypeenum',
    create_type=False,
)

organization_cost_period_enum = postgresql.ENUM(
    'YEAR', 'MONTH', 'HOUR',
    name='organizationcostperiodenum',
    create_type=False,
)

organization_cost_visibility_enum = postgresql.ENUM(
    'ADMIN', 'MANAGER', 'ALL',
    name='organizationcostvisibilityenum',
    create_type=False,
)

user_status_enum = postgresql.ENUM(
    'PENDING', 'ACTIVE',
    name='userstatusenum',
    create_type=False,
)

calendar_type_enum = postgresql.ENUM(
    'GOOGLE', 'GOOGLE_SERVICE',
    name='calendartypeenum',
    create_type=False,
)

organization_member_role_enum = postgresql.ENUM(
    'ADMIN', 'MEMBER',
    name='organizationmemberroleenum',
    create_type=False,
)

organization_member_status_enum = postgresql.ENUM(
    'ACTIVE', 'PENDING',
    name='organizationmemberstatusenum',
    create_type=False,
)

invitation_status_enum = postgresql.ENUM(
    'PENDING', 'ACCEPTED', 'EXPIRED',
    name='invitationstatusenum',
    create_type=False,
)

organization_team_member_type_enum = postgresql.ENUM(
    'MEMBER', 'MANAGER',
    name='organizationteammembertypeenum',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- CREATE ENUM TYPES ---
    for enum in (
        organization_cost_type_enum,
        organization_cost_period_enum,
        organization_cost_visibility_enum,
        user_status_enum,
        calendar_type_enum,
        organization_member_role_enum,
        organization_member_status_enum,
        invitation_status_enum,
        organization_team_member_type_enum,
    ):
        enum.create(bind, checkfirst=True)

    # --- TABLES ---
    op.create_table(
        'organizations_currency',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('currency_code', sa.String(3), nullable=False),
        sa.Column('cost_avg', sa.Numeric()),
        sa.Column('cost_is_active', sa.Boolean(), nullable=False),
        sa.Column('cost_type', organization_cost_type_enum),
        sa.Column('cost_period', organization_cost_period_enum),
        sa.Column('cost_visibility', organization_cost_visibility_enum),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(128)),
        sa.Column('email', sa.String(128), nullable=False, unique=True),
        sa.Column('photo_url', sa.Text()),
        sa.Column('status', user_status_enum, nullable=False),
    )

    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String()),
        sa.Column('organizations_currency_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['organizations_currency_id'],
            ['organizations_currency.id'],
        ),
    )

    op.create_table(
        'users_access_info',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=False, unique=True),
        sa.Column('calendar_email', sa.String(128)),
        sa.Column('type', calendar_type_enum, nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('access_token_expiry', sa.DateTime(timezone=True)),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    op.create_table(
        'invitations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('token', sa.String(255), nullable=False, unique=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('role', organization_member_role_enum, nullable=False),
        sa.Column('status', invitation_status_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
    )

    op.create_table(
        'organization_members',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('hourly_cost', sa.Numeric()),
        sa.Column('status', organization_member_status_enum, nullable=False),
        sa.Column('role', organization_member_role_enum, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
    )

    op.create_table(
        'organization_teams',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
    )

    op.create_table(
        'agenda_beta',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_member_id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(
            ['organization_member_id'],
            ['organization_members.id'],
            ondelete='CASCADE',
        ),
    )

    op.create_table(
        'organization_team_members',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('organization_member_id', sa.UUID(), nullable=False),
        sa.Column('type', organization_team_member_type_enum, nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['organization_teams.id']),
        sa.ForeignKeyConstraint(['organization_member_id'], ['organization_members.id']),
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table('organization_team_members')
    op.drop_table('agenda_beta')
    op.drop_table('organization_teams')
    op.drop_table('organization_members')
    op.drop_table('invitations')
    op.drop_table('users_access_info')
    op.drop_table('organizations')
    op.drop_table('users')
    op.drop_table('organizations_currency')

    for enum in (
        organization_team_member_type_enum,
        invitation_status_enum,
        organization_member_status_enum,
        organization_member_role_enum,
        calendar_type_enum,
        user_status_enum,
        organization_cost_visibility_enum,
        organization_cost_period_enum,
        organization_cost_type_enum,
    ):
        enum.drop(bind, checkfirst=True)
