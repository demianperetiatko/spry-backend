from __future__ import annotations

from enum import Enum


class OrganizationPermission(str, Enum):
    MEMBERS_VIEW = "members:view"
    MEMBERS_CREATE = "members:create"
    MEMBERS_EDIT = "members:edit"
    MEMBERS_DELETE = "members:delete"

    TEAMS_VIEW = "teams:view"
    TEAMS_CREATE = "teams:create"
    TEAMS_EDIT = "teams:edit"
    TEAMS_DELETE = "teams:delete"

    MEETINGS_COSTS_VIEW = "meetings-costs:view"

    ANALYTICS_ORGANIZATION_VIEW = "analytics-organization:view"
    ANALYTICS_MEMBERS_VIEW = "analytics-members:view"

    FINANCE_VIEW = "finance:view"
