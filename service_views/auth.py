import os
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse


from models import get_db, Organization, OrganizationMember, OrganizationMemberStatus, OrganizationMemberRole

from models import get_db, OrganizationMember
from models.repositories.super_admin_repository import SuperAdminRepository
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from utils.google_api import create_google_login_uri, handle_callback_and_get_user_info
from utils.middleware import get_auth_member

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

FRONTEND_DOMAIN = "https://app.spryplan.com" if os.getenv('APP_ENV') == "prod" else "http://localhost:3000"


@router.get("/")
async def auth(member: OrganizationMember = Depends(get_auth_member), db: Session = Depends(get_db)):
    def get_user_type(user, db):
        organization_repository = OrganizationRepository(db)
        if organization_repository.is_user_owner_of_organization(user.id):
            return "owner"
        elif organization_repository.is_user_manager_of_organization(user.email):
            return "manager"
        return "member"

    return {
        "id": member.id,
        "photo_url": member.photo_url,
        "email": member.email,
        "name": member.name,
        "type": get_user_type(member, db),
    }


@router.get("/google/")
async def login_google():
    uri = create_google_login_uri()
    return {
        "uri": uri,
    }


@router.get("/callback/google/")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)
    state = request.query_params.get("state")
    authorization_response = str(request.url)
    user_info = handle_callback_and_get_user_info(state, authorization_response)
    email = user_info["email"]
    member = org_member_repository.find_by_email(email)
    if member is None:
        return RedirectResponse(f"{FRONTEND_DOMAIN}/user-not-found")
    else:
        is_new_user = False
        member.google_access_token = user_info['google_access_token'],
        member.google_refresh_token = user_info['google_refresh_token'],
        if member.status == OrganizationMemberStatus.PENDING:
            is_new_user = True
            member.name = user_info.get('name')
            member.photo_url = user_info.get('picture')
            member.status = OrganizationMemberStatus.ACTIVE
        org_member_repository.update(member)
        request.session["user_id"] = str(member.id)
        redirect_url = f"{FRONTEND_DOMAIN}/onboarding" if is_new_user else FRONTEND_DOMAIN
        return RedirectResponse(redirect_url)


@router.get("/logout/")
async def logout(request: Request):
    request.session.clear()


@router.get("/delete")
async def delete_user(request: Request, member: OrganizationMember = Depends(get_auth_member),
                      db: Session = Depends(get_db)):
    request.session.clear()
    if member.role == OrganizationMember.ADMIN:
        return {
            "status": "error",
        }
    org_member_repository = OrganizationMemberRepository(db)
    org_member_repository.delete(member)
