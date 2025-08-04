from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b5bbe7f05ce1'
down_revision = 'fedb931cdf82'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE organizationmemberstatusenum AS ENUM ('active', 'pending')")
    op.execute("CREATE TYPE organizationmemberroleenum AS ENUM ('owner', 'member')")
    op.execute("CREATE TYPE organizationteammembertypeenum AS ENUM ('member', 'manager')")
    op.execute("CREATE TYPE organizationcostperiodenum AS ENUM ('year', 'month', 'hour')")
    op.execute("CREATE TYPE organizationcostvisibilityenum AS ENUM ('owner', 'manager', 'all')")
    op.execute("CREATE TYPE organizationcosttypeenum AS ENUM ('per_member', 'average')")

    op.create_table('organization_member_calendars',
                    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('type', sa.Enum('google', 'google_services', name='calendartypeenum'), nullable=False),
                    sa.Column('access_token', sa.Text(), nullable=False),
                    sa.Column('access_token_expiry', sa.DateTime(), nullable=True),
                    sa.Column('refresh_token', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['member_id'], ['organization_members.id']),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.execute("UPDATE organization_members SET status = LOWER(status)")
    op.execute("UPDATE organization_members SET role = LOWER(role) WHERE role IS NOT NULL")
    op.execute("UPDATE organization_team_members SET type = LOWER(type)")
    op.execute("UPDATE organizations SET cost_period = LOWER(cost_period) WHERE cost_period IS NOT NULL")
    op.execute("UPDATE organizations SET cost_visibility = LOWER(cost_visibility) WHERE cost_visibility IS NOT NULL")
    op.execute("UPDATE organizations SET cost_type = LOWER(cost_type) WHERE cost_type IS NOT NULL")

    op.alter_column(
        'organization_members', 'status',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('active', 'pending', name='organizationmemberstatusenum', create_type=False),
        existing_nullable=False,
        postgresql_using="status::organizationmemberstatusenum"
    )
    op.alter_column(
        'organization_members', 'role',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('owner', 'member', name='organizationmemberroleenum', create_type=False),
        existing_nullable=True,
        postgresql_using="role::organizationmemberroleenum"
    )
    op.alter_column(
        'organization_team_members', 'type',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('member', 'manager', name='organizationteammembertypeenum', create_type=False),
        existing_nullable=False,
        postgresql_using="type::organizationteammembertypeenum"
    )
    op.alter_column(
        'organizations', 'cost_period',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('year', 'month', 'hour', name='organizationcostperiodenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_period::organizationcostperiodenum"
    )
    op.alter_column(
        'organizations', 'cost_visibility',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('owner', 'manager', 'all', name='organizationcostvisibilityenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_visibility::organizationcostvisibilityenum"
    )
    op.alter_column(
        'organizations', 'cost_type',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('per_member', 'average', name='organizationcosttypeenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_type::organizationcosttypeenum"
    )


def downgrade():
    op.alter_column(
        'organizations', 'cost_type',
        existing_type=sa.Enum('per_member', 'average', name='organizationcosttypeenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_type::VARCHAR"
    )
    op.alter_column(
        'organizations', 'cost_visibility',
        existing_type=sa.Enum('owner', 'manager', 'all', name='organizationcostvisibilityenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_visibility::VARCHAR"
    )
    op.alter_column(
        'organizations', 'cost_period',
        existing_type=sa.Enum('year', 'month', 'hour', name='organizationcostperiodenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_period::VARCHAR"
    )
    op.alter_column(
        'organization_team_members', 'type',
        existing_type=sa.Enum('member', 'manager', name='organizationteammembertypeenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
        postgresql_using="type::VARCHAR"
    )
    op.alter_column(
        'organization_members', 'role',
        existing_type=sa.Enum('owner', 'member', name='organizationmemberroleenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="role::VARCHAR"
    )
    op.alter_column(
        'organization_members', 'status',
        existing_type=sa.Enum('active', 'pending', name='organizationmemberstatusenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
        postgresql_using="status::VARCHAR"
    )

    op.drop_table('organization_member_calendars')

    op.execute("DROP TYPE IF EXISTS calendartypeenum")
    op.execute("DROP TYPE IF EXISTS organizationcosttypeenum")
    op.execute("DROP TYPE IF EXISTS organizationcostvisibilityenum")
    op.execute("DROP TYPE IF EXISTS organizationcostperiodenum")
    op.execute("DROP TYPE IF EXISTS organizationteammembertypeenum")
    op.execute("DROP TYPE IF EXISTS organizationmemberroleenum")
    op.execute("DROP TYPE IF EXISTS organizationmemberstatusenum")
