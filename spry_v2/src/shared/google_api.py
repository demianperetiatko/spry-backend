from __future__ import annotations

from authlib.integrations.requests_client import OAuth2Session
from pydantic import BaseModel

from src.core.config import settings


class GoogleUserInfo(BaseModel):
    email: str
    name: str | None = None
    photo_url: str | None = None
    access_token: str
    refresh_token: str | None = None
    expires_in: int


class GoogleAPI:
    @classmethod
    def create_login_uri(cls) -> str:
        client = OAuth2Session(
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            scope=" ".join(settings.GOOGLE_SCOPE),
            redirect_uri=settings.google_redirect_uri,
            token_endpoint=settings.GOOGLE_TOKEN_ENDPOINT,
        )
        uri, _state = client.create_authorization_url(
            settings.GOOGLE_AUTHORIZATION_ENDPOINT,
            response_type="code",
            access_type="offline",
            prompt="consent",
        )
        return uri

    @classmethod
    def handle_callback_and_get_user_info(cls, state: str, authorization_response: str) -> GoogleUserInfo:
        client = OAuth2Session(
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            scope=" ".join(settings.GOOGLE_SCOPE),
            redirect_uri=settings.google_redirect_uri,
            token_endpoint=settings.GOOGLE_TOKEN_ENDPOINT,
        )
        token = client.fetch_token(settings.GOOGLE_TOKEN_ENDPOINT, authorization_response=authorization_response, state=state)
        google_access_token = token["access_token"]
        google_refresh_token = token.get("refresh_token", None)
        expires_in_seconds = token.get("expires_in", 3600)
        user_info = client.get(settings.GOOGLE_USERINFO_ENDPOINT).json()
        return GoogleUserInfo(
            email=user_info.get("email"),
            name=user_info.get("name"),
            photo_url=user_info.get("picture"),
            access_token=google_access_token,
            refresh_token=google_refresh_token,
            expires_in=expires_in_seconds,
        )


def get_google_api() -> type[GoogleAPI]:
    return GoogleAPI
