from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b5bbe7f05ce1'
down_revision = 'fedb931cdf82'
branch_labels = None
depends_on = None


def upgrade():
    # Створюємо enum типи, якщо їх ще немає
    op.execute("CREATE TYPE organizationmemberstatusenum AS ENUM ('ACTIVE', 'PENDING')")
    op.execute("CREATE TYPE organizationmemberroleenum AS ENUM ('OWNER', 'MEMBER')")
    op.execute("CREATE TYPE organizationteammembertypeenum AS ENUM ('MEMBER', 'MANAGER')")
    op.execute("CREATE TYPE organizationcostperiodenum AS ENUM ('YEAR', 'MONTH', 'HOUR')")
    op.execute("CREATE TYPE organizationcostvisibilityenum AS ENUM ('OWNER', 'MANAGER', 'ALL')")
    op.execute("CREATE TYPE organizationcosttypeenum AS ENUM ('PER_MEMBER', 'AVERAGE')")

    op.create_table('organization_member_calendars',
                    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('type', sa.Enum('GOOGLE', 'GOOGLE_SERVICES', name='calendartypeenum'), nullable=False),
                    sa.Column('access_token', sa.Text(), nullable=False),
                    sa.Column('access_token_expiry', sa.DateTime(), nullable=True),
                    sa.Column('refresh_token', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['member_id'], ['organization_members.id']),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.execute("UPDATE organization_members SET status = UPPER(status)")
    op.execute("UPDATE organization_members SET role = UPPER(role) WHERE role IS NOT NULL")
    op.execute("UPDATE organization_team_members SET type = UPPER(type)")
    op.execute("UPDATE organizations SET cost_period = UPPER(cost_period) WHERE cost_period IS NOT NULL")
    op.execute("UPDATE organizations SET cost_visibility = UPPER(cost_visibility) WHERE cost_visibility IS NOT NULL")
    op.execute("UPDATE organizations SET cost_type = UPPER(cost_type) WHERE cost_type IS NOT NULL")

    # Зміна типів колонок з використанням postgresql_using для правильного кастингу
    op.alter_column(
        'organization_members', 'status',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('ACTIVE', 'PENDING', name='organizationmemberstatusenum', create_type=False),
        existing_nullable=False,
        postgresql_using="status::organizationmemberstatusenum"
    )
    op.alter_column(
        'organization_members', 'role',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('OWNER', 'MEMBER', name='organizationmemberroleenum', create_type=False),
        existing_nullable=True,
        postgresql_using="role::organizationmemberroleenum"
    )
    op.alter_column(
        'organization_team_members', 'type',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('MEMBER', 'MANAGER', name='organizationteammembertypeenum', create_type=False),
        existing_nullable=False,
        postgresql_using="type::organizationteammembertypeenum"
    )
    op.alter_column(
        'organizations', 'cost_period',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('YEAR', 'MONTH', 'HOUR', name='organizationcostperiodenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_period::organizationcostperiodenum"
    )
    op.alter_column(
        'organizations', 'cost_visibility',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('OWNER', 'MANAGER', 'ALL', name='organizationcostvisibilityenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_visibility::organizationcostvisibilityenum"
    )
    op.alter_column(
        'organizations', 'cost_type',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('PER_MEMBER', 'AVERAGE', name='organizationcosttypeenum', create_type=False),
        existing_nullable=True,
        postgresql_using="cost_type::organizationcosttypeenum"
    )


def downgrade():
    op.alter_column(
        'organizations', 'cost_type',
        existing_type=sa.Enum('PER_MEMBER', 'AVERAGE', name='organizationcosttypeenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_type::VARCHAR"
    )
    op.alter_column(
        'organizations', 'cost_visibility',
        existing_type=sa.Enum('OWNER', 'MANAGER', 'ALL', name='organizationcostvisibilityenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_visibility::VARCHAR"
    )
    op.alter_column(
        'organizations', 'cost_period',
        existing_type=sa.Enum('YEAR', 'MONTH', 'HOUR', name='organizationcostperiodenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="cost_period::VARCHAR"
    )
    op.alter_column(
        'organization_team_members', 'type',
        existing_type=sa.Enum('MEMBER', 'MANAGER', name='organizationteammembertypeenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
        postgresql_using="type::VARCHAR"
    )
    op.alter_column(
        'organization_members', 'role',
        existing_type=sa.Enum('OWNER', 'MEMBER', name='organizationmemberroleenum'),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        postgresql_using="role::VARCHAR"
    )
    op.alter_column(
        'organization_members', 'status',
        existing_type=sa.Enum('ACTIVE', 'PENDING', name='organizationmemberstatusenum'),
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
