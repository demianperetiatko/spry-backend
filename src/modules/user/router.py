from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from src.modules.auth.dependency import get_auth_user
from src.modules.user.model import User
from src.modules.user.schemas import OrganizationMemberInfo, UserInfo
from src.modules.user.service import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/profile", response_model=UserInfo)
async def get_user_profile(
    user: User = Depends(get_auth_user),
) -> UserInfo:
    return UserInfo.model_validate(user)


@router.put("/profile", response_model=UserInfo)
async def update_user_profile(
    user: User = Depends(get_auth_user),
    name: str | None = Form(default=None),
    photo_file: UploadFile | None = File(None),
    service: UserService = Depends(get_user_service),
) -> UserInfo:
    updated_user = await service.update_user_profile(user, name=name, photo_file=photo_file)
    return UserInfo.model_validate(updated_user)


@router.delete("/delete")
async def delete_user(
    request: Request,
    user: User = Depends(get_auth_user),
    service: UserService = Depends(get_user_service),
) -> dict[str, str]:
    await service.delete_user(user)
    request.session.clear()
    return {"status": "ok"}


@router.get("/organizations", response_model=list[OrganizationMemberInfo])
async def get_user_organizations(
    user: User = Depends(get_auth_user),
    service: UserService = Depends(get_user_service),
) -> list[OrganizationMemberInfo]:
    return await service.get_user_organizations(user)
