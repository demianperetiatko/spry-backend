import os
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from models import get_db, User

from utils.services import create_google_login_uri, update_user_after_google_login, authenticated_user

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

FRONTEND_DOMAIN = "https://app.spryplan.com" if os.getenv('APP_ENV') == "prod" else "http://localhost:3000"


@router.get("/")
async def auth(user: User = Depends(authenticated_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }


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
    if user.email == "sazhagutalin@gmail.com":
        return RedirectResponse("http://localhost:3000/")
    redirect_url = f"{FRONTEND_DOMAIN}/onboarding/profile" if is_new_user else FRONTEND_DOMAIN
    return RedirectResponse(redirect_url)


@router.get("/logout/")
async def logout(request: Request):
    request.session.clear()


@router.get("/delete")
async def delete_user(request: Request, user: User = Depends(authenticated_user)):
    request.session.clear()
