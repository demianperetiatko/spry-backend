from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.core.database.transaction import atomic
from src.modules.enums import OrganizationMemberRoleEnum, OrganizationMemberStatusEnum
from src.modules.organization_member.exceptions import MemberNotActiveError
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.organization_team.exceptions import (
    TeamMemberNotInOrganizationError,
    TeamNotFoundError,
    TeamPermissionError,
)
from src.modules.organization_team.model import OrganizationTeam, OrganizationTeamMember
from src.modules.organization_team.repository import (
    OrganizationTeamMemberRepository,
    OrganizationTeamRepository,
    get_organization_team_member_repository,
    get_organization_team_repository,
)
from src.modules.organization_team.schemas import (
    CreateTeamRequest,
    TeamMemberRequest,
    TeamMemberResponse,
    TeamResponse,
    TeamsListResponse,
    UpdateTeamRequest,
)


class OrganizationTeamService:
    def __init__(
        self,
        team_repo: OrganizationTeamRepository,
        team_member_repo: OrganizationTeamMemberRepository,
        member_repo: OrganizationMemberRepository,
        session: AsyncSession,
    ) -> None:
        self.team_repo = team_repo
        self.team_member_repo = team_member_repo
        self.member_repo = member_repo
        self.session = session

    @staticmethod
    def _map_to_response(team: OrganizationTeam) -> TeamResponse:
        team_member_responses = [
            TeamMemberResponse(
                id=team_member.member.user.id,
                organization_member_id=team_member.organization_member_id,
                user_id=team_member.member.user.id,
                email=team_member.member.user.email,
                name=team_member.member.user.name,
                photo_url=team_member.member.user.photo_url,
                role=team_member.type.value,
            )
            for team_member in team.team_members
            if team_member.member and team_member.member.user
        ]

        return TeamResponse(
            id=team.id,
            name=team.name,
            members=team_member_responses,
            members_count=len(team_member_responses),
        )

    async def get_teams(
        self,
        organization_id: uuid.UUID,
    ) -> TeamsListResponse:
        teams = await self.team_repo.get_teams_by_organization_id(organization_id)
        return TeamsListResponse(
            total_count=len(teams),
            data=[self._map_to_response(team) for team in teams],
        )

    async def get_team_by_id(
        self,
        team_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> TeamResponse:
        team = await self.team_repo.get_by_id_and_organization_id(team_id, organization_id)
        if not team:
            raise TeamNotFoundError()

        return self._map_to_response(team)

    async def create_team(
        self,
        organization_id: uuid.UUID,
        payload: CreateTeamRequest,
    ) -> TeamResponse:
        member_id_map = await self._resolve_member_ids_by_users(payload.team_members, organization_id)
        await self._ensure_members_active(member_id_map.values())
        member_ids = list(member_id_map.values())
        await self._validate_members_belong_to_org(member_ids, organization_id)

        async with atomic(self.session):
            team = OrganizationTeam(name=payload.name, organization_id=organization_id)
            await self.team_repo.create(team)

            new_members = [
                OrganizationTeamMember(
                    team_id=team.id,
                    organization_member_id=member_id_map[member_req.user_id],
                    type=member_req.role,
                )
                for member_req in payload.team_members
            ]
            await self.team_member_repo.bulk_create(new_members)

        return await self.get_team_by_id(team.id, organization_id)

    async def update_team(
        self,
        team_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: UpdateTeamRequest,
        auth_member: OrganizationMember,
    ) -> TeamResponse:
        team = await self.team_repo.get_by_id_and_organization_id(team_id, organization_id)
        if not team:
            raise TeamNotFoundError()

        if not await self._can_member_edit_team(team, auth_member):
            raise TeamPermissionError()

        member_id_map = await self._resolve_member_ids_by_users(payload.team_members, organization_id)
        await self._ensure_members_active(member_id_map.values())
        member_ids = list(member_id_map.values())
        await self._validate_members_belong_to_org(member_ids, organization_id)

        async with atomic(self.session):
            team.name = payload.name
            await self.team_repo.update(team)

            await self.team_member_repo.delete_by_team_id(team.id)
            await self.session.flush()

            new_members = [
                OrganizationTeamMember(
                    team_id=team.id,
                    organization_member_id=member_id_map[member_req.user_id],
                    type=member_req.role,
                )
                for member_req in payload.team_members
            ]
            await self.team_member_repo.bulk_create(new_members)

        self.session.expire(team, ["team_members"])

        return await self.get_team_by_id(team.id, organization_id)

    async def delete_team(
        self,
        team_id: uuid.UUID,
        organization_id: uuid.UUID,
        auth_member: OrganizationMember,
    ) -> None:
        team = await self.team_repo.get_by_id_and_organization_id(team_id, organization_id)
        if not team:
            raise TeamNotFoundError()

        if not await self._can_member_edit_team(team, auth_member):
            raise TeamPermissionError()

        await self.team_repo.remove(team)

    async def _can_member_edit_team(
        self,
        team: OrganizationTeam,
        editor: OrganizationMember,
    ) -> bool:
        if editor.status != OrganizationMemberStatusEnum.ACTIVE:
            return False
        if editor.role == OrganizationMemberRoleEnum.ADMIN:
            return True
        return await self.team_member_repo.is_manager(team.id, editor.id)

    async def _validate_members_belong_to_org(
        self,
        member_ids: list[uuid.UUID],
        organization_id: uuid.UUID,
    ) -> None:
        count = await self.member_repo.count_members_in_org(member_ids, organization_id)
        if count != len(set(member_ids)):
            raise TeamMemberNotInOrganizationError()

    async def _resolve_member_ids_by_users(
        self,
        team_members: list[TeamMemberRequest],
        organization_id: uuid.UUID,
    ) -> dict[uuid.UUID, uuid.UUID]:
        """
        Map incoming user_ids to organization_member_ids within the same organization.
        """
        mapping: dict[uuid.UUID, uuid.UUID] = {}
        for member_req in team_members:
            member = await self.member_repo.get_by_user_id_and_organization_id(member_req.user_id, organization_id)
            if not member:
                raise TeamMemberNotInOrganizationError()
            mapping[member_req.user_id] = member.id
        return mapping

    async def _ensure_members_active(self, member_ids: list[uuid.UUID]) -> None:
        if not member_ids:
            return
        for member_id in member_ids:
            member = await self.member_repo.find_by_id(member_id)
            if not member or member.status != OrganizationMemberStatusEnum.ACTIVE:
                raise MemberNotActiveError()


async def get_organization_team_service(
    team_repo: OrganizationTeamRepository = Depends(get_organization_team_repository),
    team_member_repo: OrganizationTeamMemberRepository = Depends(get_organization_team_member_repository),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    session: AsyncSession = Depends(get_session),
) -> OrganizationTeamService:
    return OrganizationTeamService(
        team_repo=team_repo,
        team_member_repo=team_member_repo,
        member_repo=member_repo,
        session=session,
    )
