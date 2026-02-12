from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks, Depends, Request

from src.core.config import settings
from src.modules.calendar.dependency import CalendarServiceDep, get_calendar_service
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.user.model import User
from src.modules.user.schemas import (
    UserInfo,
    UserWithOrganizationsInfo,
)
from src.modules.user.service import UserService, get_user_service
from src.shared.google_api import GoogleAPI, get_google_api


class AuthService:
    def __init__(
        self,
        google_api: type[GoogleAPI],
        user_service: UserService,
        member_repo: OrganizationMemberRepository,
        calendar_service: CalendarServiceDep | None = None,
    ) -> None:
        self.google_api = google_api
        self.user_service = user_service
        self.member_repo = member_repo
        self.calendar_service = calendar_service

    async def get_google_login_uri(self) -> dict[str, str]:
        uri = self.google_api.create_login_uri()
        return {"uri": uri}

    async def handle_google_callback(
        self,
        state: str,
        authorization_response: str,
        request: Request,
        background_tasks: BackgroundTasks | None = None,
    ) -> str:
        user_info = self.google_api.handle_callback_and_get_user_info(state, authorization_response)

        user, is_new_user = await self.user_service.authenticate_with_google(user_info)

        if not user:
            return f"{self._get_frontend_domain()}/user-not-found"

        request.session["user_id"] = str(user.id)

        if self.calendar_service and background_tasks:
            background_tasks.add_task(self.calendar_service.ensure_calendar_health, user.id)

        redirect_url = f"{self._get_frontend_domain()}/onboarding/profile" if is_new_user else self._get_frontend_domain()
        return redirect_url

    async def get_user_info(
        self,
        user: User,
        organization_id: UUID | None = None,
    ) -> UserInfo | UserWithOrganizationsInfo:
        if organization_id:
            member = await self.member_repo.get_by_user_id_and_organization_id(user.id, organization_id)
            if not member:
                return UserInfo.model_validate(user)

            organizations = await self.user_service.get_user_organizations(user)
            return UserWithOrganizationsInfo(
                id=user.id,
                email=user.email,
                name=user.name,
                photo_url=user.photo_url,
                organizations=organizations,
            )

        return UserInfo.model_validate(user)

    @staticmethod
    async def logout(request: Request) -> None:
        request.session.clear()

    @staticmethod
    def _get_frontend_domain() -> str:
        return settings.frontend_domain


async def get_auth_service(
    google_api: type[GoogleAPI] = Depends(get_google_api),
    user_service: UserService = Depends(get_user_service),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    calendar_service: CalendarServiceDep | None = Depends(get_calendar_service, use_cache=False),
) -> AuthService:
    return AuthService(
        google_api=google_api,
        user_service=user_service,
        member_repo=member_repo,
        calendar_service=calendar_service,
    )
