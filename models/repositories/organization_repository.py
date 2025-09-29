from typing import TypeVar

from models import Organization
from models import OrganizationMember
from models import OrganizationMemberRoleEnum
from models import OrganizationTeamMember
from models import OrganizationTeamMemberTypeEnum
from models.repositories import BaseRepo

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_by_user_email(self, email: str) -> Organization:
        return (
            self.session.query(Organization)
            .join(
                OrganizationMember,
                Organization.id == OrganizationMember.organization_id,
                isouter=True,
            )
            .filter(OrganizationMember.email == email)
            .first()
        )

    def is_user_owner_of_organization(self, user_id: str) -> bool:
        res = (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.id == user_id)
            .filter(OrganizationMember.role == OrganizationMemberRoleEnum.admin)
            .first()
        )
        return True if res else False

    def is_user_manager_of_organization(self, email: str) -> bool:
        res = (
            self.session.query(OrganizationMember)
            .join(
                OrganizationTeamMember,
                OrganizationMember.id == OrganizationTeamMember.member_id,
            )
            .filter(OrganizationMember.email == email)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager)
            .first()
        )
        return True if res else False
