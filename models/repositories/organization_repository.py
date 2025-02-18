import uuid
from typing import TypeVar, List, Optional

from models.repositories import BaseRepo
from models import User, Organization, OrganizationMember, OrganizationMemberStatus, OrganizationTeamMemberType
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

    def is_user_owner_of_organization(self, user_id: int) -> bool:
        res = self.session.query(Organization).filter(Organization.create_user_id == user_id).first()
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

    def update_member_cost(self, organization_id: int, average_cost: Optional[float]):
        formatted_cost = f"{average_cost:.2f}" if average_cost is not None else None
        self.session.query(OrganizationMember).filter(OrganizationMember.organization_id == organization_id).update(
            {OrganizationMember.cost: formatted_cost}, synchronize_session=False
        )
        return self.session.commit()

    def find_by_member_id(self, organization_id: int, member_id: int) -> OrganizationMember:
        return (
            self.session.query(
                OrganizationMember.id,
                User.name,
                User.photo_url,
                OrganizationMember.email,
                OrganizationMember.cost,
                OrganizationMember.status,
            )
            .filter(OrganizationMember.id == member_id)
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def find_by_member_email(self, organization_id: int, email: str) -> OrganizationMember:
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.email == email)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def find_by_organization_id(self, organization_id: int) -> List[dict]:
        org_team_repository = OrganizationTeamRepository(self.session)
        members = (
            self.session.query(
                OrganizationMember.id,
                User.name,
                User.photo_url,
                OrganizationMember.email,
                literal("-").label("department"),
                OrganizationMember.cost,
                OrganizationMember.status,
            )
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationMember.organization_id == organization_id)
            .all()
        )
        res = []
        for member in members:
            info = {
                "id": member.id,
                "name": member.name,
                "photo_url": member.photo_url,
                "email": member.email,
                "cost": float(member.cost) if member.cost else None,
                "status": member.status,
                "department": member.department,
                "teams": org_team_repository.find_by_member_id(member.id)
            }
            res.append(info)
        return res


class OrganizationTeamRepository(BaseRepo[OrganizationTeam]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeam)

    def find_by_organization_id(self, organization_id: int) -> List[OrganizationTeam]:
        subquery = (
            self.session.query(
                OrganizationTeamMember.team_id,
                func.count(OrganizationTeamMember.member_id).label("member_count")
            )
            .group_by(OrganizationTeamMember.team_id)
            .subquery()
        )

        return (
            self.session.query(
                OrganizationTeam.id,
                OrganizationTeam.name,
                OrganizationTeamMember.member_id.label("manager_id"),
                OrganizationMember.email.label("manager_email"),
                User.name.label("manager_name"),
                User.photo_url.label("manager_photo"),
                func.coalesce(subquery.c.member_count, 0).label("team_members_count")
            )
            .join(OrganizationTeamMember, OrganizationTeamMember.team_id == OrganizationTeam.id)
            .join(OrganizationMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .outerjoin(subquery, OrganizationTeam.id == subquery.c.team_id)
            .filter(OrganizationTeam.organization_id == organization_id)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberType.MANAGER)
            .all()
        )

    def find_by_team_id(self, organization_id: int, team_id: int) -> OrganizationTeam:
        return (
            self.session.query(OrganizationTeam)
            .filter(OrganizationTeam.organization_id == organization_id)
            .filter(OrganizationTeam.id == team_id)
            .first()
        )

    def find_by_member_id(self, member_id: id) -> List[OrganizationTeam]:
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

    def find_by_team_id(self, team_id: int) -> List[OrganizationTeamMember]:
        return (
            self.session.query(
                OrganizationTeamMember.id,
                OrganizationTeamMember.member_id,
                OrganizationMember.email,
                User.name,
                User.photo_url,
                OrganizationTeamMember.type
            )
            .join(OrganizationMember, OrganizationMember.id == OrganizationTeamMember.member_id)
            .join(User, OrganizationMember.email == User.email, isouter=True)
            .filter(OrganizationTeamMember.team_id == team_id)
            .all()
        )

    def delete_all_team_member(self, team_id: int) -> None:
        return self.session.query(OrganizationTeamMember).filter(OrganizationTeamMember.team_id == team_id).delete()
