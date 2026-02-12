from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.session import get_session
from src.core.database.transaction import atomic
from src.modules.enums import (
    InvitationStatusEnum,
    OrganizationCostTypeEnum,
    OrganizationMemberRoleEnum,
    OrganizationMemberStatusEnum,
    UserStatusEnum,
)
from src.modules.invitation.model import Invitation
from src.modules.invitation.repository import (
    InvitationRepository,
    get_invitation_repository,
)
from src.modules.organization.exceptions import (
    OrganizationAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
)
from src.modules.organization.model import Organization, OrganizationCurrency
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    OrganizationRepository,
    get_organization_currency_repository,
    get_organization_repository,
)
from src.modules.organization.schemas import (
    CostSettingsResponse,
    OrganizationOnboardRequest,
    UpdateCostSettingsRequest,
)
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.user.model import User
from src.modules.user.repository import UserRepository, get_user_repository
from src.shared.cost import calculate_hourly_cost
from src.shared.email import EmailService, get_email_service


class OrganizationService:
    def __init__(
        self,
        org_repo: OrganizationRepository,
        org_member_repo: OrganizationMemberRepository,
        org_currency_repo: OrganizationCurrencyRepository,
        user_repo: UserRepository,
        invitation_repo: InvitationRepository,
        email_service: EmailService,
        session: AsyncSession,
    ) -> None:
        self.org_repo = org_repo
        self.org_member_repo = org_member_repo
        self.org_currency_repo = org_currency_repo
        self.user_repo = user_repo
        self.invitation_repo = invitation_repo
        self.email_service = email_service
        self.session = session

    async def onboard_organization(
        self,
        payload: OrganizationOnboardRequest,
    ) -> Organization:
        admin_email = str(payload.admin_email)

        async with atomic(self.session):
            existing_org = await self.org_repo.get_by_name(payload.name)
            if existing_org:
                raise OrganizationAlreadyExistsError()

            currency = OrganizationCurrency()
            await self.org_currency_repo.create(currency)

            org = Organization(name=payload.name, organizations_currency_id=currency.id)
            await self.org_repo.create(org)

            user = await self.user_repo.get_by_email(admin_email)
            if not user:
                user = User(email=admin_email, status=UserStatusEnum.PENDING)
                await self.user_repo.create(user)

            if settings.SINGLE_ORG_POLICY_ENABLED:
                memberships = await self.org_member_repo.get_active_members_by_user_id(user.id)
                conflict = next((m for m in memberships if m.organization_id != org.id), None)
                if conflict:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Single-organization policy temporarily enforced for frontend v1.",
                    )

            existing_member = await self.org_member_repo.get_by_user_id_and_organization_id(
                user.id,
                org.id,
            )
            if existing_member:
                raise OrganizationMemberAlreadyExistsError()

            invitation_token = str(uuid.uuid4())
            invitation = Invitation(
                token=invitation_token,
                user_id=user.id,
                organization_id=org.id,
                role=OrganizationMemberRoleEnum.ADMIN,
                status=InvitationStatusEnum.PENDING,
            )
            await self.invitation_repo.create(invitation)

            admin_member = OrganizationMember(
                user_id=user.id,
                organization_id=org.id,
                role=OrganizationMemberRoleEnum.ADMIN,
                status=OrganizationMemberStatusEnum.PENDING,
            )
            await self.org_member_repo.create(admin_member)

            invitation_link = settings.get_invitation_link(invitation_token)

        await self.email_service.send_invitation(
            admin_email,
            invitation_link,
            org.name,
            is_admin=True,
        )

        return org

    async def get_cost_settings(self, organization_id: uuid.UUID) -> CostSettingsResponse:
        org = await self.org_repo.find_by_id(organization_id)
        currency = await self.org_currency_repo.find_by_id(org.organizations_currency_id)

        return CostSettingsResponse.model_validate(currency)

    async def update_cost_settings(
        self,
        organization_id: uuid.UUID,
        cost_settings: UpdateCostSettingsRequest,
    ) -> CostSettingsResponse:
        org = await self.org_repo.find_by_id(organization_id)
        currency_entity = await self.org_currency_repo.find_by_id(org.organizations_currency_id)

        previous_state = {
            "is_active": currency_entity.cost_is_active,
            "cost_type": currency_entity.cost_type,
        }

        currency_entity.cost_is_active = cost_settings.cost_is_active

        if cost_settings.cost_is_active:
            currency_entity.currency_code = cost_settings.currency_code
            currency_entity.cost_period = cost_settings.cost_period
            currency_entity.cost_visibility = cost_settings.cost_visibility
            currency_entity.cost_type = cost_settings.cost_type
            currency_entity.cost_avg = cost_settings.cost_avg
        else:
            currency_entity.cost_period = None
            currency_entity.cost_visibility = None
            currency_entity.cost_type = None
            currency_entity.cost_avg = None
            # TODO: Fix this - leave currency_code unchanged because it cannot be NULL

        await self.org_currency_repo.update(currency_entity)

        await self._sync_member_costs(organization_id, previous_state, currency_entity)

        return CostSettingsResponse.model_validate(currency_entity)

    async def _sync_member_costs(self, org_id: uuid.UUID, prev_state: dict, currency_entity: OrganizationCurrency) -> None:
        is_disabled_now = not currency_entity.cost_is_active
        if prev_state["is_active"] and is_disabled_now:
            await self.org_member_repo.update_organization_members_cost(org_id, None)
            return

        is_average_mode = currency_entity.cost_is_active and currency_entity.cost_type == OrganizationCostTypeEnum.AVERAGE
        if is_average_mode:
            hourly_rate = calculate_hourly_cost(currency_entity.cost_avg, currency_entity.cost_period)
            await self.org_member_repo.update_organization_members_cost(org_id, hourly_rate)
            return

        was_average_mode = prev_state["cost_type"] == OrganizationCostTypeEnum.AVERAGE
        switched_from_average = prev_state["is_active"] and was_average_mode and not is_average_mode

        if switched_from_average:
            await self.org_member_repo.update_organization_members_cost(org_id, None)

        return


async def get_organization_service(
    org_repo: OrganizationRepository = Depends(get_organization_repository),
    org_member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    org_currency_repo: OrganizationCurrencyRepository = Depends(get_organization_currency_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    email_service: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_session),
) -> OrganizationService:
    return OrganizationService(
        org_repo=org_repo,
        org_member_repo=org_member_repo,
        org_currency_repo=org_currency_repo,
        user_repo=user_repo,
        invitation_repo=invitation_repo,
        email_service=email_service,
        session=session,
    )
