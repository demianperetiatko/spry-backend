from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.session import get_session
from src.core.database.transaction import atomic
from src.modules.enums import (
    InvitationStatusEnum,
    OrganizationMemberRoleEnum,
    OrganizationMemberStatusEnum,
    OrganizationTeamMemberTypeEnum,
    UserStatusEnum,
)
from src.modules.invitation.model import Invitation
from src.modules.invitation.repository import InvitationRepository, get_invitation_repository
from src.modules.organization.exceptions import OrganizationMemberAlreadyExistsError
from src.modules.organization.model import OrganizationCurrency
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    get_organization_currency_repository,
)
from src.modules.organization_member.exceptions import (
    CannotEditMemberError,
    MemberAlreadyActiveError,
    MemberAlreadyExistsError,
    MemberNotActiveError,
    MemberNotFoundError,
    OrganizationCurrencyNotConfiguredError,
)
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.organization_member.schemas import (
    MemberResponse,
    MemberTeamDetailResponse,
    PaginatedMembersResponse,
    UpdateMemberRequest,
)
from src.modules.organization_team.exceptions import TeamNotFoundError
from src.modules.organization_team.model import OrganizationTeamMember
from src.modules.organization_team.repository import (
    OrganizationTeamMemberRepository,
    OrganizationTeamRepository,
    get_organization_team_member_repository,
    get_organization_team_repository,
)
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions, get_permissions
from src.modules.user.exceptions import UserNotFoundError
from src.modules.user.model import User
from src.modules.user.repository import UserRepository, get_user_repository
from src.shared.cost import calculate_hourly_cost, calculate_total_cost
from src.shared.email import EmailService, get_email_service


class OrganizationMemberService:
    def __init__(
        self,
        member_repo: OrganizationMemberRepository,
        user_repo: UserRepository,
        invitation_repo: InvitationRepository,
        currency_repo: OrganizationCurrencyRepository,
        team_repo: OrganizationTeamRepository,
        team_member_repo: OrganizationTeamMemberRepository,
        permissions_service: type[Permissions],
        email_service: EmailService,
        session: AsyncSession,
    ) -> None:
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.invitation_repo = invitation_repo
        self.currency_repo = currency_repo
        self.team_repo = team_repo
        self.team_member_repo = team_member_repo
        self.permissions_service = permissions_service
        self.email_service = email_service
        self.session = session

    async def get_organization_members(
        self,
        organization_id: uuid.UUID,
        auth_member: OrganizationMember,
        currency: OrganizationCurrency,
        search_query: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> PaginatedMembersResponse:
        members, total = await self.member_repo.get_members_by_organization_id(
            organization_id=organization_id,
            search_query=search_query,
            limit=limit,
            offset=offset,
        )

        has_finance_permission = await self.permissions_service.member_has_permission(
            member=auth_member,
            permission=OrganizationPermission.FINANCE_VIEW,
            currency=currency,
            member_repo=self.member_repo,
        )

        all_team_ids = set()
        for member in members:
            for team_member in member.team_members:
                if team_member.team_id:
                    all_team_ids.add(team_member.team_id)

        team_manager_map = {}
        if all_team_ids:
            team_manager_map = await self.team_member_repo.get_managers_by_team_ids(list(all_team_ids))

        results = []
        for member in members:
            cost = None
            if member.hourly_cost and has_finance_permission:
                cost = calculate_total_cost(member.hourly_cost, currency.cost_period)

            teams_details = []
            for team_member in member.team_members:
                team = team_member.team
                if not team:
                    continue

                team_roles = []
                if team_member.type == OrganizationTeamMemberTypeEnum.MANAGER:
                    team_roles.append("manager")
                else:
                    team_roles.append("member")

                teams_details.append(
                    MemberTeamDetailResponse(
                        team_id=team.id,
                        team_name=team.name,
                        manager_id=team_manager_map.get(team.id),
                        roles=team_roles,
                    )
                )

            results.append(
                MemberResponse(
                    id=member.user.id,
                    name=member.user.name if member.user else None,
                    photo_url=member.user.photo_url if member.user else None,
                    email=member.user.email,
                    status=member.status.value,
                    cost=cost,
                    teams=teams_details,
                )
            )

        return PaginatedMembersResponse(
            count=total,
            limit=limit or 20,
            offset=offset or 0,
            results=results,
        )

    async def add_members_to_organization(
        self,
        organization_id: uuid.UUID,
        emails: list[str],
        auth_member: OrganizationMember,
        organization_name: str,
    ) -> None:
        existing_emails = []

        for email in emails:
            existing_member = await self.member_repo.get_by_email_and_organization_id(email, organization_id)
            if existing_member:
                existing_emails.append(email)

        if existing_emails:
            raise MemberAlreadyExistsError(existing_emails)

        existing_users = await self.user_repo.get_by_emails(emails)
        existing_users_map = {user.email.lower(): user for user in existing_users}

        async with atomic(self.session):
            for email in emails:
                email_lower = email.lower()

                user = existing_users_map.get(email_lower)
                if not user:
                    user = User(email=email, status=UserStatusEnum.PENDING)
                    await self.user_repo.create(user)
                    existing_users_map[email_lower] = user

                if settings.SINGLE_ORG_POLICY_ENABLED:
                    memberships = await self.member_repo.get_active_members_by_user_id(user.id)
                    conflict = next((m for m in memberships if m.organization_id != organization_id), None)
                    if conflict:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Single-organization policy temporarily enforced for frontend v1.",
                        )

                existing_member = await self.member_repo.get_by_user_id_and_organization_id(
                    user.id,
                    organization_id,
                )
                if existing_member:
                    raise OrganizationMemberAlreadyExistsError()

                invitation_token = str(uuid.uuid4())
                invitation = Invitation(
                    token=invitation_token,
                    user_id=user.id,
                    organization_id=organization_id,
                    role=OrganizationMemberRoleEnum.MEMBER,
                    status=InvitationStatusEnum.PENDING,
                )
                await self.invitation_repo.create(invitation)

                member = OrganizationMember(
                    user_id=user.id,
                    organization_id=organization_id,
                    role=OrganizationMemberRoleEnum.MEMBER,
                    status=OrganizationMemberStatusEnum.PENDING,
                )
                await self.member_repo.create(member)

                invitation_link = settings.get_invitation_link(invitation_token)
                await self.email_service.send_invitation(
                    email=email,
                    link=invitation_link,
                    organization_name=organization_name,
                    is_admin=False,
                    administrator_name=auth_member.user.name,
                )

    async def update_member(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        update_data: UpdateMemberRequest,
        auth_member: OrganizationMember,
        currency: OrganizationCurrency,
    ) -> MemberResponse:
        member = await self.member_repo.get_by_user_id_and_organization_id(user_id, organization_id)
        if not member:
            raise MemberNotFoundError()

        if not await self._can_member_edit_member(auth_member, member):
            raise CannotEditMemberError()

        if member.status != OrganizationMemberStatusEnum.ACTIVE:
            raise MemberNotActiveError()

        async with atomic(self.session):
            if update_data.cost is not None:
                if not currency or not currency.cost_period:
                    raise OrganizationCurrencyNotConfiguredError()
                hourly_cost = calculate_hourly_cost(update_data.cost, currency.cost_period)
                member.hourly_cost = hourly_cost
            elif update_data.cost is None and "cost" in update_data.model_dump(exclude_unset=True):
                member.hourly_cost = None

            await self.member_repo.update(member)

            if update_data.teams is not None:
                existing_memberships = await self.team_member_repo.get_by_member_id(member.id)
                existing_by_team = {tm.team_id: tm for tm in existing_memberships if tm.team_id}

                requested_map: dict[uuid.UUID, bool] = {}
                for team_data in update_data.teams:
                    if not team_data.team_id:
                        continue
                    team = await self.team_repo.get_by_id_and_organization_id(
                        team_data.team_id,
                        organization_id,
                    )
                    if not team:
                        raise TeamNotFoundError()
                    requested_map[team.id] = team_data.is_manager

                to_add = [team_id for team_id in requested_map if team_id not in existing_by_team]
                to_update = [
                    team_id
                    for team_id in requested_map
                    if team_id in existing_by_team
                    and (existing_by_team[team_id].type == OrganizationTeamMemberTypeEnum.MANAGER) != requested_map[team_id]
                ]
                to_remove = [team_id for team_id in existing_by_team if team_id not in requested_map]

                new_team_members = []
                for team_id in to_add:
                    member_type = (
                        OrganizationTeamMemberTypeEnum.MANAGER
                        if requested_map[team_id]
                        else OrganizationTeamMemberTypeEnum.MEMBER
                    )
                    new_team_members.append(
                        OrganizationTeamMember(
                            team_id=team_id,
                            organization_member_id=member.id,
                            type=member_type,
                        )
                    )

                if new_team_members:
                    await self.team_member_repo.bulk_create(new_team_members)

                for team_id in to_update:
                    member_type = (
                        OrganizationTeamMemberTypeEnum.MANAGER
                        if requested_map[team_id]
                        else OrganizationTeamMemberTypeEnum.MEMBER
                    )
                    await self.team_member_repo.update_member_type(team_id, member.id, member_type)

                if to_remove:
                    await self.team_member_repo.delete_by_member_and_team_ids(member.id, to_remove)

        updated_member = await self.member_repo.get_by_user_id_and_organization_id(user_id, organization_id)
        if not updated_member:
            raise MemberNotFoundError()

        cost = None
        if updated_member.hourly_cost:
            has_finance_permission = await self.permissions_service.member_has_permission(
                member=auth_member,
                permission=OrganizationPermission.FINANCE_VIEW,
                currency=currency,
                member_repo=self.member_repo,
            )
            if has_finance_permission:
                cost = calculate_total_cost(updated_member.hourly_cost, currency.cost_period)

        teams_details = []
        for team_member in updated_member.team_members:
            if not team_member.team:
                continue

            team_roles = []
            if team_member.type == OrganizationTeamMemberTypeEnum.MANAGER:
                team_roles.append("manager")
            else:
                team_roles.append("member")

            manager_id = await self.team_member_repo.find_manager_id(team_member.team.id)

            teams_details.append(
                MemberTeamDetailResponse(
                    team_id=team_member.team.id,
                    team_name=team_member.team.name,
                    manager_id=manager_id,
                    roles=team_roles,
                )
            )

        return MemberResponse(
            id=updated_member.user.id,
            name=updated_member.user.name if updated_member.user else None,
            photo_url=updated_member.user.photo_url if updated_member.user else None,
            email=updated_member.user.email,
            status=updated_member.status.value,
            cost=cost,
            teams=teams_details,
        )

    async def delete_member(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        member = await self.member_repo.get_by_user_id_and_organization_id(user_id, organization_id)
        if not member:
            raise MemberNotFoundError()

        await self.member_repo.remove(member)

    async def resend_invitation(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        auth_member: OrganizationMember,
        organization_name: str,
    ) -> None:
        member = await self.member_repo.get_by_user_id_and_organization_id(user_id, organization_id)
        if not member:
            raise MemberNotFoundError()

        if member.status == OrganizationMemberStatusEnum.ACTIVE:
            raise MemberAlreadyActiveError()

        if member.status != OrganizationMemberStatusEnum.PENDING:
            raise MemberAlreadyActiveError()

        invitation = await self.invitation_repo.get_by_user_id_and_organization_id(
            member.user_id,
            organization_id,
        )

        if invitation and invitation.status == InvitationStatusEnum.ACCEPTED:
            raise MemberAlreadyActiveError()

        if not invitation or invitation.status != InvitationStatusEnum.PENDING:
            invitation_token = str(uuid.uuid4())
            invitation = Invitation(
                token=invitation_token,
                user_id=member.user_id,
                organization_id=organization_id,
                role=member.role,
                status=InvitationStatusEnum.PENDING,
            )
            await self.invitation_repo.create(invitation)
        else:
            invitation_token = invitation.token

        user = await self.user_repo.get_by_id(member.user_id)
        if not user:
            raise UserNotFoundError()

        invitation_link = settings.get_invitation_link(invitation_token)
        await self.email_service.send_invitation(
            email=user.email,
            link=invitation_link,
            organization_name=organization_name,
            is_admin=False,
            administrator_name=auth_member.user.name if auth_member.user else None,
        )

    async def _can_member_edit_member(
        self,
        editor: OrganizationMember,
        target: OrganizationMember,
    ) -> bool:
        if editor.role == OrganizationMemberRoleEnum.ADMIN:
            return True

        is_manager = await self.member_repo.is_manager_of_organization(editor)
        if not is_manager:
            return False

        return await self.member_repo.are_members_in_same_team(editor.id, target.id)


async def get_organization_member_service(
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    currency_repo: OrganizationCurrencyRepository = Depends(get_organization_currency_repository),
    team_repo: OrganizationTeamRepository = Depends(get_organization_team_repository),
    team_member_repo: OrganizationTeamMemberRepository = Depends(get_organization_team_member_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    email_service: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMemberService:
    return OrganizationMemberService(
        member_repo=member_repo,
        user_repo=user_repo,
        invitation_repo=invitation_repo,
        currency_repo=currency_repo,
        team_repo=team_repo,
        team_member_repo=team_member_repo,
        permissions_service=permissions_service,
        email_service=email_service,
        session=session,
    )
