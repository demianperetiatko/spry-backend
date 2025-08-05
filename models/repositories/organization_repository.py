import uuid
from typing import TypeVar, List, Optional

from models.repositories import BaseRepo
from models import Organization, OrganizationMember, OrganizationMemberStatusEnum, OrganizationTeamMemberTypeEnum, \
    OrganizationMemberRoleEnum
from models import OrganizationTeam, OrganizationTeamMember
from sqlalchemy.sql import literal
from sqlalchemy.sql import func

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_by_user_email(self, email: str) -> Organization:
        return (
            self.session.query(Organization)
            .join(OrganizationMember, Organization.id == OrganizationMember.organization_id, isouter=True)
            .filter(OrganizationMember.email == email)
            .first()
        )

    def is_user_owner_of_organization(self, user_id: str) -> bool:
        res = self.session.query(OrganizationMember).filter(OrganizationMember.id == user_id).filter(
            OrganizationMember.role == OrganizationMemberRoleEnum.owner).first()
        return True if res else False

    def is_user_manager_of_organization(self, email: str) -> bool:
        res = (
            self.session.query(OrganizationMember)
            .join(OrganizationTeamMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .filter(OrganizationMember.email == email)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager)
            .first()
        )
        return True if res else False


from .organization_member_repository import OrganizationMemberRepository

from .organization_team_repository import OrganizationTeamRepository, OrganizationTeamMemberRepository
