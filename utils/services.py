import os
from fastapi import Request, HTTPException, Depends, Header

from sqlalchemy.orm import Session

from models import get_db, User, Organization, OrganizationMember, OrganizationMemberStatus
from models.repositories.user_repository import UserRepository
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
    user_repository = UserRepository(db)
    token = client.fetch_token(
        TOKEN_ENDPOINT,
        authorization_response=authorization_response,
        state=state
    )
    google_access_token = token["access_token"]
    google_refresh_token = token.get("refresh_token", None)
    user_info = client.get(USERINFO_ENDPOINT).json()
    email = user_info.get("email")
    if email not in [
        "bohdan.dobosevych@gmail.com",
        "demian.peretiatko@gmail.com",
        "kostyantin1408@gmail.com",
        "dobosevych@gmail.com",
        "o.dobosevych@geniusee.com",
        "dudeson26@gmail.com",
        "demian@flowlity.com",
        "sazhagutalin@gmail.com",
        "nastyalada@gmail.com",
        "darka.azhnyuk@gmail.com"
    ]:
        return None
    user = user_repository.find_by_email(email)
    is_new_user = False
    if not user:
        user = User(
            name=user_info.get('name'),
            photo_url=user_info.get('picture'),
            email=email,
            google_access_token=google_access_token,
            google_refresh_token=google_refresh_token,
        )
        user_repository.create(user)
    else:
        user.google_access_token = google_access_token
        user.google_refresh_token = google_refresh_token
        user_repository.update(user)

    organization_repository = OrganizationRepository(db)
    org = organization_repository.find_by_user(user)
    if org is None:
        is_new_user = True
        organization_member_repository = OrganizationMemberRepository(db)
        org = Organization(create_user_id=user.id)
        organization_repository.create(org)
        member = OrganizationMember(
            organization_id=org.id,
            email=user.email,
            status=OrganizationMemberStatus.ACTIVE,
            added_by_id=user.id,
        )
        organization_member_repository.create(member)
    return user, is_new_user


def authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_repository = UserRepository(db)
    user = user_repository.find_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
