from sqlalchemy.orm import Session
from fastapi import Depends

from models import get_db, Organization, OrganizationMember, OrganizationMemberRole, OrganizationCostVisibility

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository


def get_member_permissions(member: OrganizationMember, db):
    org_manager_repository = OrganizationMemberRepository(db)

    permissions = []
    # members
    if member.role == OrganizationMemberRole.OWNER:
        permissions.extend([
            "members:view",
            "members:create",
            "members:edit",
            "members:delete",
        ])
    else:
        permissions.append("members:view")

    # team
    if member.role == OrganizationMemberRole.OWNER:
        permissions.extend([
            "teams:view",
            "teams:create",
            "teams:edit",
            "teams:delete",
        ])
    else:
        permissions.append("teams:view")

    # meetings-costs
    if member.role == OrganizationMemberRole.OWNER:
        permissions.append("meetings-costs:view")

    # analytics
    permissions.extend([
        "analytics-organization:view",
        "analytics-members:view",
    ])

    # finance:view
    if member.role == OrganizationMemberRole.OWNER:
        permissions.append("finance:view")
    elif member.organization.cost_is_active == True:
        if (member.organization.cost_visibility == OrganizationCostVisibility.MANAGER
                and org_manager_repository.is_manager_of_organization(member.id)):
            permissions.append("finance:view")
        elif member.organization.cost_visibility == OrganizationCostVisibility.ALL:
            permissions.append("finance:view")

    return permissions


def member_has_permissions(member, action, db):
    has_permissions = action in get_member_permissions(member, db)
    return has_permissions
