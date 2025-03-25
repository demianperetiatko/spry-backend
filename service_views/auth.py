import os
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from models import get_db, User
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from utils.services import create_google_login_uri, update_user_after_google_login
from utils.middleware import get_auth_user

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

FRONTEND_DOMAIN = "https://app.spryplan.com" if os.getenv('APP_ENV') == "prod" else "http://localhost:3000"


@router.get("/")
async def auth(user: User = Depends(get_auth_user), db: Session = Depends(get_db)):
    def get_user_type(user, db):
        organization_repository = OrganizationRepository(db)
        if organization_repository.is_user_owner_of_organization(user.id):
            return "owner"
        elif organization_repository.is_user_manager_of_organization(user.email):
            return "manager"
        return "member"

    return {
        "id": user.id,
        "photo_url": user.photo_url,
        "email": user.email,
        "name": user.name,
        "type": get_user_type(user, db),
    }


@router.get("/member/")
async def auth_member(user: User = Depends(get_auth_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    query_members = org_member_repository.query_find_by_organization_id(org.id)
    return query_members.all()


@router.get("/google/")
async def login_google():
    uri = create_google_login_uri()
    return {
        "uri": uri,
    }


@router.get("/callback/google/")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    state = request.query_params.get("state")
    authorization_response = str(request.url)
    user, is_new_user = update_user_after_google_login(state, authorization_response, db)
    if user is None:
        return {
            "status": "error",
        }
    request.session["user_id"] = user.id
    redirect_url = f"{FRONTEND_DOMAIN}/onboarding" if is_new_user else FRONTEND_DOMAIN
    return RedirectResponse(redirect_url)


@router.get("/logout/")
async def logout(request: Request):
    request.session.clear()


@router.get("/delete")
async def delete_user(request: Request, user: User = Depends(get_auth_user)):
    request.session.clear()
