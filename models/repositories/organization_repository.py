import uuid
from typing import TypeVar, List, Optional

from models.repositories import BaseRepo
from models import Organization, OrganizationMember, OrganizationMemberStatus, OrganizationTeamMemberType, OrganizationMemberRole
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
        res = self.session.query(OrganizationMember).filter(OrganizationMember.id == user_id).filter(OrganizationMember.role == OrganizationMemberRole.OWNER).first()
        return True if res else False

    def is_user_manager_of_organization(self, email: str) -> bool:
        res = (
            self.session.query(OrganizationMember)
            .join(OrganizationTeamMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .filter(OrganizationMember.email == email)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberType.MANAGER)
            .first()
        )
        return True if res else False


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)

    def update_member_cost(self, organization_id, average_cost: Optional[float]):
        formatted_cost = f"{average_cost:.2f}" if average_cost is not None else None
        self.session.query(OrganizationMember).filter(OrganizationMember.organization_id == organization_id).update(
            {OrganizationMember.hourly_cost: formatted_cost}, synchronize_session=False
        )
        return self.session.commit()

    def find_by_member_id(self, organization_id, member_id) -> OrganizationMember:
        return (
            self.session.query(
                OrganizationMember.id,
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationMember.email,
                OrganizationMember.hourly_cost,
                OrganizationMember.status,
                OrganizationMember.google_refresh_token
            )
            .filter(OrganizationMember.id == member_id)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )
    def find_by_email(self, email: str) -> OrganizationMember:
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.email == email)
            .first()
        )
    def find_by_member_email(self, organization_id, email: str) -> OrganizationMember:
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.email == email)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def query_find_by_organization_id(self, organization_id):
        return (
            self.session.query(
                OrganizationMember.id,
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationMember.email,
                OrganizationMember.hourly_cost,
                OrganizationMember.status,
                OrganizationMember.google_refresh_token
            )
            .filter(OrganizationMember.organization_id == organization_id)
        )

    def find_by_organization_id(self, organization_id):
        return self.query_find_by_organization_id(organization_id).all()

    def is_manager_of_organization(self, member_id) -> bool:
        res = (
            self.session.query(OrganizationTeamMember)
            .filter(OrganizationTeamMember.member_id == member_id)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberType.MANAGER)
            .first()
        )
        return True if res else False

class OrganizationTeamRepository(BaseRepo[OrganizationTeam]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeam)

    def query_find_by_organization_id(self, organization_id) -> List[OrganizationTeam]:
        return (
            self.session.query(
                OrganizationTeam.id,
                OrganizationTeam.name,
                OrganizationTeamMember.member_id.label("manager_id"),
                OrganizationMember.email.label("manager_email"),
                OrganizationMember.name.label("manager_name"),
                OrganizationMember.photo_url.label("manager_photo"),
            )
            .join(OrganizationTeamMember, OrganizationTeamMember.team_id == OrganizationTeam.id)
            .join(OrganizationMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .filter(OrganizationTeam.organization_id == organization_id)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberType.MANAGER)
        )

    def find_by_organization_id(self, organization_id):
        return self.query_find_by_organization_id(organization_id).all()

    def find_by_team_id(self, organization_id, team_id) -> OrganizationTeam:
        return (
            self.session.query(OrganizationTeam)
            .filter(OrganizationTeam.organization_id == organization_id)
            .filter(OrganizationTeam.id == team_id)
            .first()
        )

    def find_by_member_id(self, member_id) -> List[OrganizationTeam]:
        return (
            self.session.query(
                OrganizationTeam.id.label("team_id"),
                OrganizationTeam.name.label("team_name"),
                (OrganizationTeamMember.type == OrganizationTeamMemberType.MANAGER).label("is_manager"),
            )
            .join(OrganizationTeamMember, OrganizationTeam.id == OrganizationTeamMember.team_id)
            .filter(OrganizationTeamMember.member_id == member_id)
            .all()
        )


class OrganizationTeamMemberRepository(BaseRepo[OrganizationTeamMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeamMember)

    def query_find_by_team_id(self, team_id):
        return (
            self.session.query(
                OrganizationTeamMember.id,
                OrganizationTeamMember.member_id,
                OrganizationMember.email,
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationTeamMember.type,
                OrganizationMember.hourly_cost,
                OrganizationMember.google_refresh_token,
            )
            .join(OrganizationMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .filter(OrganizationTeamMember.team_id == team_id)
        )

    def find_by_team_id(self, team_id):
        return self.query_find_by_team_id(team_id).all()

    def delete_all_team_member(self, team_id) -> None:
        return self.session.query(OrganizationTeamMember).filter(OrganizationTeamMember.team_id == team_id).delete()
