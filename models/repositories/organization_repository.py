import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import User, Organization, OrganizationMember, OrganizationMemberStatus

from sqlalchemy.sql import literal

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_organization(self, user: User) -> Organization:
        return (
            self.session.query(Organization)
            .join(OrganizationMember, Organization.id == OrganizationMember.organization_id, isouter=True)
            .filter(
                (Organization.create_user_id == user.id) |
                (OrganizationMember.email == user.email)
            )
            .first()
        )


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)

    def find_member(self, organization_id: int, member_id: int) -> OrganizationMember:
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.id == member_id)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def find_members(self, organization_id: int) -> Organization:
        print(OrganizationMemberStatus.PENDING.value)
        return (
            self.session.query(
                OrganizationMember.id,
                User.name,
                User.photo_url,
                OrganizationMember.email,
                literal("-").label("department"),
                literal("-").label("team"),
                literal("-").label("rate"),
                literal(OrganizationMemberStatus.PENDING.value).label("status"),
            )
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationMember.organization_id == organization_id)
            .all()
        )