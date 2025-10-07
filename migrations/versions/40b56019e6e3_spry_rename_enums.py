"""SPRY rename enums

Revision ID: 40b56019e6e3
Revises: 3e384429ab9c
Create Date: 2025-08-11 14:20:50.692838
"""

from typing import Sequence
from typing import Union

from alembic import op

revision: str = "40b56019e6e3"
down_revision: Union[str, None] = "3e384429ab9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # OrganizationCostVisibilityEnum
    op.execute("ALTER TYPE organizationcostvisibilityenum RENAME TO organizationcostvisibilityenum_old;")
    op.execute("CREATE TYPE organizationcostvisibilityenum AS ENUM ('admin', 'manager', 'all')")
    op.execute("ALTER TABLE organizations ALTER COLUMN cost_visibility TYPE text")
    op.execute("""
        UPDATE organizations
        SET cost_visibility = CASE cost_visibility
            WHEN 'owner' THEN 'admin'
            ELSE cost_visibility
        END
    """)
    op.execute("""
        ALTER TABLE organizations
        ALTER COLUMN cost_visibility TYPE organizationcostvisibilityenum
        USING cost_visibility::organizationcostvisibilityenum
    """)
    op.execute("DROP TYPE organizationcostvisibilityenum_old;")

    # OrganizationMemberRoleEnum
    op.execute("ALTER TYPE organizationmemberroleenum RENAME TO organizationmemberroleenum_old;")
    op.execute("CREATE TYPE organizationmemberroleenum AS ENUM ('admin', 'member')")
    op.execute("ALTER TABLE organization_members ALTER COLUMN role TYPE text")
    op.execute("""
        UPDATE organization_members
        SET role = CASE role
            WHEN 'owner' THEN 'admin'
            ELSE role
        END
    """)
    op.execute("""
        ALTER TABLE organization_members
        ALTER COLUMN role TYPE organizationmemberroleenum
        USING role::organizationmemberroleenum
    """)
    op.execute("DROP TYPE organizationmemberroleenum_old;")

    # CalendarTypeEnum
    op.execute("ALTER TYPE calendartypeenum RENAME TO calendartypeenum_old;")
    op.execute("CREATE TYPE calendartypeenum AS ENUM ('google', 'google_service')")
    op.execute("ALTER TABLE organization_member_calendars ALTER COLUMN type TYPE text")
    op.execute("""
        UPDATE organization_member_calendars
        SET type = CASE type
            WHEN 'google_services' THEN 'google_service'
            ELSE type
        END
    """)
    op.execute("""
        ALTER TABLE organization_member_calendars
        ALTER COLUMN type TYPE calendartypeenum
        USING type::calendartypeenum
    """)
    op.execute("DROP TYPE calendartypeenum_old;")


def downgrade() -> None:
    # OrganizationCostVisibilityEnum
    op.execute("ALTER TYPE organizationcostvisibilityenum RENAME TO organizationcostvisibilityenum_old;")
    op.execute("CREATE TYPE organizationcostvisibilityenum AS ENUM ('owner', 'manager', 'all')")
    op.execute("ALTER TABLE organizations ALTER COLUMN cost_visibility TYPE text")
    op.execute("""
        UPDATE organizations
        SET cost_visibility = CASE cost_visibility
            WHEN 'admin' THEN 'owner'
            ELSE cost_visibility
        END
    """)
    op.execute("""
        ALTER TABLE organizations
        ALTER COLUMN cost_visibility TYPE organizationcostvisibilityenum
        USING cost_visibility::organizationcostvisibilityenum
    """)
    op.execute("DROP TYPE organizationcostvisibilityenum_old;")

    # OrganizationMemberRoleEnum
    op.execute("ALTER TYPE organizationmemberroleenum RENAME TO organizationmemberroleenum_old;")
    op.execute("CREATE TYPE organizationmemberroleenum AS ENUM ('owner', 'member')")
    op.execute("ALTER TABLE organization_members ALTER COLUMN role TYPE text")
    op.execute("""
        UPDATE organization_members
        SET role = CASE role
            WHEN 'admin' THEN 'owner'
            ELSE role
        END
    """)
    op.execute("""
        ALTER TABLE organization_members
        ALTER COLUMN role TYPE organizationmemberroleenum
        USING role::organizationmemberroleenum
    """)
    op.execute("DROP TYPE organizationmemberroleenum_old;")

    # CalendarTypeEnum
    op.execute("ALTER TYPE calendartypeenum RENAME TO calendartypeenum_old;")
    op.execute("CREATE TYPE calendartypeenum AS ENUM ('google', 'google_services')")
    op.execute("ALTER TABLE organization_member_calendars ALTER COLUMN type TYPE text")
    op.execute("""
        UPDATE organization_member_calendars
        SET type = CASE type
            WHEN 'google_service' THEN 'google_services'
            ELSE type
        END
    """)
    op.execute("""
        ALTER TABLE organization_member_calendars
        ALTER COLUMN type TYPE calendartypeenum
        USING type::calendartypeenum
    """)
    op.execute("DROP TYPE calendartypeenum_old;")
