import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import Organization, OrganizationMember

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_by_create_user_id(self, user_id: int) -> Organization:
        return self.session.query(Organization).filter(Organization.create_user_id == user_id).first()

    def find_by_member(self, organization_id: str) -> List[OrganizationMember]:
        # return self.session.query(TeamMember).all()
        return self.session.query(OrganizationMember).filter(OrganizationMember.organization_id == organization_id).all()


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)
