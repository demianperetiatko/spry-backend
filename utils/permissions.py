from models import OrganizationCostVisibilityEnum
from models import OrganizationMember
from models import OrganizationMemberRoleEnum
from models.repositories.organization_member_repository import OrganizationMemberRepository


def get_member_permissions(member: OrganizationMember, db):
    org_manager_repository = OrganizationMemberRepository(db)

    permissions = []
    # members
    if member.role == OrganizationMemberRoleEnum.admin:
        permissions.extend(
            [
                "members:view",
                "members:create",
                "members:edit",
                "members:delete",
            ]
        )
    elif org_manager_repository.is_manager_of_organization(member.id):
        permissions.extend(
            [
                "members:view",
                "members:edit",
            ]
        )
    else:
        permissions.append("members:view")

    # team
    if member.role == OrganizationMemberRoleEnum.admin:
        permissions.extend(
            [
                "teams:view",
                "teams:create",
                "teams:edit",
                "teams:delete",
            ]
        )
    elif org_manager_repository.is_manager_of_organization(member.id):
        permissions.extend(
            [
                "teams:view",
                "teams:edit",
            ]
        )
    else:
        permissions.append("teams:view")

    # meetings-costs
    if member.role == OrganizationMemberRoleEnum.admin:
        permissions.append("meetings-costs:view")

    # analytics
    permissions.extend(
        [
            "analytics-organization:view",
            "analytics-members:view",
        ]
    )

    # finance:view
    if member.role == OrganizationMemberRoleEnum.admin:
        permissions.append("finance:view")
    elif member.organization.cost_is_active == True:
        if (
            member.organization.cost_visibility == OrganizationCostVisibilityEnum.manager
            and org_manager_repository.is_manager_of_organization(member.id)
        ):
            permissions.append("finance:view")
        elif member.organization.cost_visibility == OrganizationCostVisibilityEnum.all:
            permissions.append("finance:view")

    return permissions


def member_has_permissions(member, action, db):
    has_permissions = action in get_member_permissions(member, db)
    return has_permissions
