from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session, sessionmanager
from src.core.database.transaction import atomic
from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.service import CalendarService
from src.modules.enums import CalendarTypeEnum, UserStatusEnum
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    get_organization_currency_repository,
)
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.service import Permissions, get_permissions
from src.modules.user.exceptions import UserIsAdminError
from src.modules.user.model import User, UserAccessInfo
from src.modules.user.repository import (
    UserAccessInfoRepository,
    UserRepository,
    get_user_access_info_repository,
    get_user_repository,
)
from src.modules.user.schemas import OrganizationMemberInfo
from src.shared.gcp_bucket import GCPBucket, get_gcp_bucket
from src.shared.google_api import GoogleUserInfo

logger = logging.getLogger(__name__)


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        user_access_info_repo: UserAccessInfoRepository,
        org_member_repo: OrganizationMemberRepository,
        currency_repo: OrganizationCurrencyRepository,
        permissions_service: type[Permissions],
        gcp_bucket: type[GCPBucket],
        session: AsyncSession,
    ) -> None:
        self.user_repo = user_repo
        self.user_access_info_repo = user_access_info_repo
        self.org_member_repo = org_member_repo
        self.currency_repo = currency_repo
        self.permissions_service = permissions_service
        self.gcp_bucket = gcp_bucket
        self.session = session

    async def update_user_profile(
        self,
        user: User,
        name: str | None = None,
        photo_file: UploadFile | None = None,
    ) -> User:
        if name:
            user.name = name
        if photo_file:
            photo_url = self.gcp_bucket.upload_file(photo_file, filename=str(user.id))
            if photo_url:
                user.photo_url = photo_url

        await self.user_repo.update(user)
        return user

    async def delete_user(self, user: User) -> None:
        is_admin = await self.org_member_repo.is_user_admin_in_any_organization(user.id)
        if is_admin:
            raise UserIsAdminError()
        await self.user_repo.remove(user)

    async def get_user_organizations(self, user: User) -> list[OrganizationMemberInfo]:
        members = await self.org_member_repo.get_active_members_by_user_id(user.id)
        organizations = []
        for member in members:
            currency = await self.currency_repo.find_by_id(member.organization.organizations_currency_id)
            permissions = await self.permissions_service.get_member_permissions(member, currency, self.org_member_repo)

            user_type = "admin" if member.role.value == "admin" else None
            if not user_type:
                is_manager = await self.org_member_repo.is_manager_of_organization(member)
                user_type = "manager" if is_manager else "member"

            organizations.append(
                OrganizationMemberInfo(
                    organization_id=member.organization_id,
                    organization_name=member.organization.name,
                    role=member.role,
                    status=member.status,
                    member_id=member.id,
                    type=user_type,
                    permissions=permissions,
                )
            )
        return organizations

    async def authenticate_with_google(self, user_info: GoogleUserInfo) -> tuple[User | None, bool]:
        user = await self.user_repo.get_by_email(user_info.email)
        if not user:
            return None, False

        is_newly_activated = False

        async with atomic(self.session):
            await self._update_google_access_tokens(user, user_info)

            if user.status != UserStatusEnum.ACTIVE:
                await self._activate_user_account(user, user_info)
                is_newly_activated = True
            else:
                # Backfill profile fields if they are missing (common for legacy users)
                updated = False
                if not user.name and user_info.name:
                    user.name = user_info.name
                    updated = True
                if not user.photo_url and user_info.photo_url:
                    user.photo_url = self.gcp_bucket.upload_file_from_url(user_info.photo_url)
                    updated = True
                if updated:
                    await self.user_repo.update(user)

        try:
            _task = asyncio.create_task(self._trigger_full_resync(user.id))  # noqa: RUF006
        except RuntimeError:
            # If no current event loop (e.g., in tests) - execute synchronously
            await self._trigger_full_resync(user.id)

        return user, is_newly_activated

    async def _update_google_access_tokens(
        self,
        user: User,
        user_info: GoogleUserInfo,
    ) -> None:
        user_access_info = await self.user_access_info_repo.get_by_user_id(user.id)

        access_token_expiry = datetime.now(timezone.utc) + timedelta(seconds=user_info.expires_in)

        if not user_access_info:
            user_access_info = UserAccessInfo(
                user_id=user.id,
                calendar_email=user.email,
                access_token=user_info.access_token,
                refresh_token=user_info.refresh_token or "",
                access_token_expiry=access_token_expiry,
                type=CalendarTypeEnum.GOOGLE,
            )
            await self.user_access_info_repo.create(user_access_info)
        else:
            user_access_info.access_token = user_info.access_token
            if user_info.refresh_token:
                user_access_info.refresh_token = user_info.refresh_token
            user_access_info.access_token_expiry = access_token_expiry
            await self.user_access_info_repo.update(user_access_info)

    async def _activate_user_account(
        self,
        user: User,
        user_info: GoogleUserInfo,
    ) -> None:
        if user_info.name:
            user.name = user_info.name
        if user_info.photo_url:
            user.photo_url = self.gcp_bucket.upload_file_from_url(user_info.photo_url)

        user.status = UserStatusEnum.ACTIVE
        await self.user_repo.update(user)

    async def _trigger_full_resync(self, user_id: uuid.UUID) -> None:
        """
        After successful login, trigger full resync of user's calendar in background.
        """
        try:
            async with sessionmanager.session() as session:
                calendar_repo = CalendarRepository(session)
                google_client = GoogleCalendarClient()
                calendar_service = CalendarService(
                    calendar_repo=calendar_repo,
                    session=session,
                    google_client=google_client,
                )
                await calendar_service.manual_resync_for_user(user_id)
        except Exception as exc:
            logger.warning("Failed to trigger full resync for user %s: %s", user_id, exc)


async def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
    user_access_info_repo: UserAccessInfoRepository = Depends(get_user_access_info_repository),
    org_member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    currency_repo: OrganizationCurrencyRepository = Depends(get_organization_currency_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    gcp_bucket: type[GCPBucket] = Depends(get_gcp_bucket),
    session: AsyncSession = Depends(get_session),
) -> UserService:
    return UserService(
        user_repo=user_repo,
        user_access_info_repo=user_access_info_repo,
        org_member_repo=org_member_repo,
        currency_repo=currency_repo,
        permissions_service=permissions_service,
        gcp_bucket=gcp_bucket,
        session=session,
    )
