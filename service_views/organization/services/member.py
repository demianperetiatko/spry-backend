from models import Organization
from models import OrganizationMember
from models import OrganizationMemberRoleEnum
from models import OrganizationTeamMemberTypeEnum
from models.repositories.organization_member_repository import OrganizationMemberRepository
from models.repositories.organization_team_member_repository import OrganizationTeamMemberRepository
from service_views.organization.schemas.member import MemberResponse
from service_views.organization.schemas.member import MemberTeamDetailResponse
from service_views.organization.schemas.member import PaginatedMembersResponse
from utils.cost import calculate_total_cost
from utils.permissions import member_has_permissions


class MemberService:
    def __init__(self, db_session):
        self.db = db_session
        self.org_member_repo = OrganizationMemberRepository(self.db)
        self.org_team_member_repo = OrganizationTeamMemberRepository(self.db)

    def get_organization_members(
        self,
        auth_member: OrganizationMember,
        auth_organization: Organization,
        name: str | None = None,
        email: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> PaginatedMembersResponse:
        can_view_cost = member_has_permissions(auth_member, "finance:view", self.db)

        query, total = self.org_member_repo.get_query_members_by_organization_id(
            organization_id=auth_member.organization_id,
            name=name,
            email=email,
            limit=limit,
            offset=offset,
        )

        members_list = query.all()
        member_ids = [member.id for member in members_list]

        all_manager_ids = self.org_team_member_repo.get_managers_ids_by_member_ids(member_ids) if member_ids else {}

        all_team_ids = {team_association.team_id for member in members_list for team_association in member.teams}

        team_manager_map = (
            self.org_team_member_repo.get_map_team_id_manager_id_by_teams_ids(list(all_team_ids)) if all_team_ids else {}
        )

        results = []
        for member in members_list:
            roles = []
            if member.role == OrganizationMemberRoleEnum.admin:
                roles.append("admin")
            if member.id in all_manager_ids:
                roles.append("manager")

            cost = None
            if member.hourly_cost and can_view_cost:
                cost = calculate_total_cost(float(member.hourly_cost), auth_organization.cost_period)

            teams_details = []
            for team_association in member.teams:
                team = team_association.team
                if not team:
                    continue

                teams_details.append(
                    MemberTeamDetailResponse(
                        team_id=team.id,
                        team_name=team.name,
                        manager_id=team_manager_map.get(team.id),
                        is_manager=(team_association.type == OrganizationTeamMemberTypeEnum.manager),
                    )
                )

            member_data = MemberResponse(
                id=member.id,
                name=member.name,
                photo_url=member.photo_url,
                email=member.email,
                status=member.status.lower(),
                roles=roles,
                cost=cost,
                teams=teams_details,
            )
            results.append(member_data)

        return PaginatedMembersResponse(
            count=total,
            limit=limit,
            offset=offset,
            results=results,
        )
