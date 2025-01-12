import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import User, Organization, OrganizationMember

from sqlalchemy.sql import literal

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_organization(self, user_id: int) -> Organization:
        return self.session.query(Organization).filter(Organization.create_user_id == user_id).first()


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)

    def find_member(self, organization_id: int) -> Organization:
        return (
            self.session.query(
                OrganizationMember.id,
                User.name,
                User.photo_url,
                OrganizationMember.email,
                literal("-").label("department"),
                literal("-").label("team"),
                literal("-").label("rate"),
                literal("active").label("status"),
            )
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationMember.organization_id == organization_id)
            .all()
        )