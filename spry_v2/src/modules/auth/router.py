from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from starlette.responses import RedirectResponse

from src.core.config import settings
from src.modules.auth.dependency import get_auth_user
from src.modules.auth.service import AuthService, get_auth_service
from src.modules.user.model import User
from src.modules.user.schemas import UserInfo, UserWithOrganizationsInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/", response_model=UserInfo | UserWithOrganizationsInfo)
async def auth(
    user: User = Depends(get_auth_user),
    organization_id: Annotated[UUID | None, Query(description="Organization ID for context")] = None,
    service: AuthService = Depends(get_auth_service),
) -> UserInfo | UserWithOrganizationsInfo:
    return await service.get_user_info(user=user, organization_id=organization_id)


@router.get("/google/")
async def login_google(
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    return await service.get_google_login_uri()


@router.get("/callback/google/")
async def auth_google(
    request: Request,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    state = request.query_params.get("state")
    if not state:
        return RedirectResponse(url=f"{settings.frontend_domain}/error")

    authorization_response = str(request.url)
    redirect_url = await service.handle_google_callback(state, authorization_response, request, background_tasks)
    return RedirectResponse(url=redirect_url)


@router.get("/logout/")
async def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    await service.logout(request)
    return {"status": "ok"}
