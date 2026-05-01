from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from src.modules.auth.dependency import get_auth_user
from src.modules.super_admin.service import SuperAdminService, get_super_admin_service
from src.modules.user.model import User
from src.modules.user.schemas import OrganizationMemberInfo, UserInfo, UserWithOrganizationsInfo
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
    await service.delete_user(user.id)
    request.session.clear()
    return {"status": "ok"}


@router.get("/me", response_model=UserWithOrganizationsInfo)
async def get_current_user(
    user: User = Depends(get_auth_user),
    service: UserService = Depends(get_user_service),
    super_admin_service: SuperAdminService = Depends(get_super_admin_service),
) -> UserWithOrganizationsInfo:
    is_super_admin = await super_admin_service.is_super_admin(user.id)
    if is_super_admin:
        organizations = await super_admin_service.get_all_organizations()
    else:
        organizations = await service.get_user_organizations(user)
    return UserWithOrganizationsInfo(
        id=user.id,
        email=user.email,
        name=user.name,
        photo_url=user.photo_url,
        organizations=organizations,
    )


@router.get("/organizations", response_model=list[OrganizationMemberInfo])
async def get_user_organizations(
    user: User = Depends(get_auth_user),
    service: UserService = Depends(get_user_service),
    super_admin_service: SuperAdminService = Depends(get_super_admin_service),
) -> list[OrganizationMemberInfo]:
    if await super_admin_service.is_super_admin(user.id):
        return await super_admin_service.get_all_organizations()
    return await service.get_user_organizations(user)
