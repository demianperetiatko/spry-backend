import os

from authlib.integrations.requests_client import OAuth2Session

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REDIRECT_URI = (
    "https://api.spryplan.com/auth/callback/google/"
    if os.getenv("APP_ENV") == "prod"
    else "http://localhost:8000/auth/callback/google/"
)
SCOPE = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

client = OAuth2Session(
    os.getenv("GOOGLE_CLIENT_ID"),
    os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=" ".join(SCOPE),
    redirect_uri=GOOGLE_REDIRECT_URI,
    token_endpoint=TOKEN_ENDPOINT,
)


def create_google_login_uri():
    uri, state = client.create_authorization_url(
        AUTHORIZATION_ENDPOINT,
        response_type="code",
        access_type="offline",
        prompt="consent",
    )
    return uri


def handle_callback_and_get_user_info(state: str, authorization_response: str):
    token = client.fetch_token(TOKEN_ENDPOINT, authorization_response=authorization_response, state=state)
    google_access_token = token["access_token"]
    google_refresh_token = token.get("refresh_token", None)
    expires_in_seconds = token.get("expires_in", 3600)
    user_info = client.get(USERINFO_ENDPOINT).json()
    return {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "photo_url": user_info.get("picture"),
        "access_token": google_access_token,
        "refresh_token": google_refresh_token,
        "expires_in": expires_in_seconds,
    }
