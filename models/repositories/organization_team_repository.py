from typing import List
from models.repositories import BaseRepo
from models import (
    OrganizationTeam,
    OrganizationTeamMember,
    OrganizationMember,
    OrganizationTeamMemberTypeEnum,
)


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
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager)
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
                (OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager).label("is_manager"),
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
        self.session.query(OrganizationTeamMember).filter(
            OrganizationTeamMember.team_id == team_id
        ).delete()
