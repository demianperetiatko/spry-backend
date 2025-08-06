import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from models import get_db, Organization, OrganizationMember, OrganizationMemberStatusEnum, OrganizationMemberRoleEnum, \
    OrganizationMemberCalendar
from models.organization_member import CalendarTypeEnum

from models.repositories.organization_repository import OrganizationRepository
from models.repositories.organization_member_repository import OrganizationMemberRepository, \
    OrganizationMemberCalendarRepository
from utils.google_api import create_google_login_uri, handle_callback_and_get_user_info
from utils.middleware import get_auth_member
from utils.permissions import get_member_permissions

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

FRONTEND_DOMAIN = "https://app.spryplan.com" if os.getenv('APP_ENV') == "prod" else "http://localhost:3000"


@router.get("/")
async def auth(
        member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)):
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
        "permissions": get_member_permissions(member, db),
    }


@router.get("/google/")
async def login_google():
    uri = create_google_login_uri()
    return {
        "uri": uri,
    }


@router.get("/callback/google/")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    org_member_repository = OrganizationMemberRepository(db)
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    state = request.query_params.get("state")
    authorization_response = str(request.url)
    user_info = handle_callback_and_get_user_info(state, authorization_response)
    email = user_info["email"]
    member = org_member_repository.find_by_email(email)
    if member is None:
        return RedirectResponse(f"{FRONTEND_DOMAIN}/user-not-found")
    else:
        is_new_user = False
        member_calendar = member_calendar_repository.find_by_member_email_and_type(
            member_id=member.id,
            calendar_email=member.email,
            calendar_type=CalendarTypeEnum.google
        )
        if not member_calendar:
            member_calendar = OrganizationMemberCalendar(
                member_id=member.id,
                calendar_email=member.email,
                access_token=user_info['access_token'],
                refresh_token=user_info['refresh_token'],
                access_token_expiry=datetime.utcnow() + timedelta(seconds=user_info['expires_in']),
                type=CalendarTypeEnum.google,
            )
            member_calendar_repository.create(member_calendar)
        else:
            member_calendar.access_token = user_info['access_token']
            member_calendar.refresh_token = user_info['refresh_token']
            member_calendar.access_token_expiry = datetime.utcnow() + timedelta(seconds=user_info['expires_in'])
            member_calendar_repository.update(member_calendar)

        if member.status == OrganizationMemberStatusEnum.pending:
            is_new_user = True
            member.name = user_info.get('name')
            member.photo_url = user_info.get('picture')
            member.status = OrganizationMemberStatusEnum.active
        org_member_repository.update(member)
        request.session["user_id"] = str(member.id)
        redirect_url = f"{FRONTEND_DOMAIN}/onboarding/profile?role={member.role}" if is_new_user else FRONTEND_DOMAIN
        return RedirectResponse(redirect_url)


@router.get("/logout/")
async def logout(request: Request):
    request.session.clear()


@router.get("/delete")
async def delete_user(request: Request, member: OrganizationMember = Depends(get_auth_member),
                      db: Session = Depends(get_db)):
    request.session.clear()
    if member.role == OrganizationMemberRoleEnum.owner:
        return {
            "status": "error",
        }
    org_member_repository = OrganizationMemberRepository(db)
    org_member_repository.delete(member)
