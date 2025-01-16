import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import User, Organization, OrganizationMember, OrganizationMemberStatus
from models import OrganizationTeam, OrganizationTeamMember
from sqlalchemy.sql import literal

T = TypeVar("T")


class OrganizationRepository(BaseRepo[Organization]):
    def __init__(self, session):
        super().__init__(session, Organization)

    def find_by_user(self, user: User) -> Organization:
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

    def find_by_member_id(self, organization_id: int, member_id: int) -> OrganizationMember:
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.id == member_id)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def find_by_organization_id(self, organization_id: int) -> Organization:
        return (
            self.session.query(
                OrganizationMember.id,
                User.name,
                User.photo_url,
                OrganizationMember.email,
                literal("-").label("department"),
                literal("-").label("team"),
                literal("-").label("rate"),
                OrganizationMember.status,
            )
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationMember.organization_id == organization_id)
            .all()
        )

class OrganizationTeamRepository(BaseRepo[OrganizationTeam]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeam)

    def find_by_organization_id(self, organization_id: int) -> List[OrganizationTeam]:
        return self.session.query(OrganizationTeam).filter(OrganizationTeam.organization_id == organization_id).all()


class OrganizationTeamMemberRepository(BaseRepo[OrganizationTeamMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeamMember)

    def find_by_team_id(self, team_id: int) -> List[OrganizationTeamMember]:
        return self.session.query(OrganizationTeamMember).filter(OrganizationTeamMember.team_id == team_id).all()
