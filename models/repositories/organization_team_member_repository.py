from uuid import UUID

from models import OrganizationTeamMember
from models import OrganizationTeamMemberTypeEnum
from models.repositories import BaseRepo


class OrganizationTeamMemberRepository(BaseRepo[OrganizationTeamMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationTeamMember)

    def get_managers_ids_by_member_ids(self, member_ids: list[int]) -> set[int]:
        if not member_ids:
            return set()

        query = (
            self.session.query(OrganizationTeamMember.member_id)
            .filter(
                OrganizationTeamMember.member_id.in_(member_ids),
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager,
            )
            .distinct()
        )
        return {member_id for member_id in query.all()}

    def get_map_team_id_manager_id_by_teams_ids(self, team_ids: list[UUID]) -> dict[UUID, UUID]:
        if not team_ids:
            return {}

        query = (
            self.session.query(OrganizationTeamMember.team_id, OrganizationTeamMember.member_id)
            .filter(
                OrganizationTeamMember.team_id.in_(team_ids),
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager,
            )
            .all()
        )  # TODO: What if we have two managers for the team?
        return {team_id: member_id for team_id, member_id in query}
