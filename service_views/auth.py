from authlib.integrations.base_client import OAuthError
from authlib.oauth2.rfc6749 import OAuth2Token
from fastapi import APIRouter, Depends, HTTPException
from datetime import timedelta
from starlette import status

from utils.services import create_access_token, create_refresh_token, token_expired, decode_token
from utils.services import oauth
from fastapi import Request
from fastapi.responses import RedirectResponse
import os

from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class GoogleUser(BaseModel):
    sub: int
    email: str
    name: str
    picture: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/callback/google"
FRONTEND_URL = os.getenv("FRONTEND_URL")

print(GOOGLE_CLIENT_ID)
print(GOOGLE_CLIENT_SECRET)
print(FRONTEND_URL)

@router.get("/google")
async def login_google(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/callback/google")
async def auth_google(request: Request):
    try:
        user_response: OAuth2Token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    print(user_response)

    # access_token = create_access_token(user.username, user.id, timedelta(days=7))
    # refresh_token = create_refresh_token(user.username, user.id, timedelta(days=14))
    access_token, refresh_token = "", ""
    return RedirectResponse(f"{FRONTEND_URL}/auth?access_token={access_token}&refresh_token={refresh_token}")


@router.post("/refresh", response_model=Token)
async def refresh_access_token(refresh_token_request: RefreshTokenRequest):
    token = refresh_token_request.refresh_token

    if token_expired(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is expired.")

    user = decode_token(token)

    access_token = create_access_token(user["sub"], user["id"], timedelta(days=7))
    refresh_token = create_refresh_token(user["sub"], user["id"], timedelta(days=14))

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
