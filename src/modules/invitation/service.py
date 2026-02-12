from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.core.database.transaction import atomic
from src.core.events import dispatcher
from src.modules.enums import InvitationStatusEnum, OrganizationMemberStatusEnum, UserStatusEnum
from src.modules.invitation.events import InvitationAcceptedEvent
from src.modules.invitation.exceptions import (
    InvitationAcceptedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    OrganizationMemberNotFoundError,
    UserAlreadyActiveInOrganizationError,
)
from src.modules.invitation.model import Invitation
from src.modules.invitation.repository import (
    InvitationRepository,
    get_invitation_repository,
)
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.user.repository import UserRepository, get_user_repository

logger = logging.getLogger(__name__)


class InvitationService:
    def __init__(
        self,
        invitation_repo: InvitationRepository,
        user_repo: UserRepository,
        org_member_repo: OrganizationMemberRepository,
        session: AsyncSession,
    ) -> None:
        self.invitation_repo = invitation_repo
        self.user_repo = user_repo
        self.org_member_repo = org_member_repo
        self.session = session

    async def accept_invitation(self, token: str) -> Invitation:
        async with atomic(self.session):
            invitation = await self.invitation_repo.get_by_token_for_update(token)
            if not invitation:
                raise InvitationNotFoundError()

            if invitation.status != InvitationStatusEnum.PENDING:
                raise InvitationAcceptedError()

            if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
                invitation.status = InvitationStatusEnum.EXPIRED
                await self.invitation_repo.update(invitation)
                raise InvitationExpiredError()

            user = await self.user_repo.get_by_id(invitation.user_id)
            if not user:
                raise InvitationNotFoundError()

            if user.status == UserStatusEnum.PENDING:
                user.status = UserStatusEnum.ACTIVE
                await self.user_repo.update(user)

            org_member = await self.org_member_repo.get_by_user_id_and_organization_id(
                invitation.user_id,
                invitation.organization_id,
            )
            if not org_member:
                raise OrganizationMemberNotFoundError()

            if org_member.status == OrganizationMemberStatusEnum.ACTIVE:
                raise UserAlreadyActiveInOrganizationError()

            if org_member.status == OrganizationMemberStatusEnum.PENDING:
                org_member.status = OrganizationMemberStatusEnum.ACTIVE
                await self.org_member_repo.update(org_member)

            invitation.status = InvitationStatusEnum.ACCEPTED
            await self.invitation_repo.update(invitation)

            user_id = invitation.user_id
            user_email = user.email
            member_id = org_member.id

        event = InvitationAcceptedEvent(
            user_id=user_id,
            member_id=member_id,
            user_email=user_email,
        )
        await dispatcher.dispatch(event)

        return invitation


async def get_invitation_service(
    invitation_repo: InvitationRepository = Depends(get_invitation_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    org_member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    session: AsyncSession = Depends(get_session),
) -> InvitationService:
    return InvitationService(
        invitation_repo=invitation_repo,
        user_repo=user_repo,
        org_member_repo=org_member_repo,
        session=session,
    )
