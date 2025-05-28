import os
import requests

from models import get_db, Organization, OrganizationMember, OrganizationMemberStatus, OrganizationMemberRole
from models.repositories.super_admin_repository import SuperAdminRepository
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from authlib.integrations.requests_client import OAuth2Session

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REDIRECT_URI = "https://api.spryplan.com/auth/callback/google/" if os.getenv(
    'APP_ENV') == "prod" else "http://localhost:8000/auth/callback/google/"
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
    token_endpoint=TOKEN_ENDPOINT
)


def create_google_login_uri():
    uri, state = client.create_authorization_url(
        AUTHORIZATION_ENDPOINT,
        response_type="code",
        access_type="offline",
        prompt="consent"
    )
    return uri


def update_user_after_google_login(state: str, authorization_response: str, db):
    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    token = client.fetch_token(
        TOKEN_ENDPOINT,
        authorization_response=authorization_response,
        state=state
    )
    google_access_token = token["access_token"]
    google_refresh_token = token.get("refresh_token", None)
    user_info = client.get(USERINFO_ENDPOINT).json()

    email = user_info.get("email")
    member = org_member_repository.find_by_email(email)
    if member is None:
        super_admin_repository = SuperAdminRepository()
        super_admin = super_admin_repository.find_by_email(email)
        if super_admin:
            org = Organization()
            org_repository.create(org)
            member = OrganizationMember(
                name=user_info.get('name'),
                photo_url=user_info.get('picture'),
                email=email,
                google_access_token=google_access_token,
                google_refresh_token=google_refresh_token,
                role=OrganizationMemberRole.OWNER
            )
            org_member_repository.create(member)
            return member, True
        return None, False
    else:
        is_new_user = False
        member.google_access_token = google_access_token
        member.google_refresh_token = google_refresh_token
        if member.status == OrganizationMemberStatus.PENDING:
            is_new_user = True
            member.status = OrganizationMemberStatus.ACTIVE
        org_member_repository.update(member)
        return member, is_new_user

def refresh_google_access_token(refresh_token: str) -> str:
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(url, data=payload)
    token_data = response.json()
    if "access_token" in token_data:
        return token_data["access_token"]
