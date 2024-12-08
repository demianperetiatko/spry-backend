from fastapi import APIRouter, Depends, HTTPException
from datetime import timedelta, datetime, timezone as tz
from typing import Annotated

from starlette import status
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, defer
from authlib.integrations.starlette_client import OAuth
import os
from jose import jwt, JWTError
from starlette.config import Config

UTC = tz.utc
ALGORITHM = "HS256"

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or None
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or None

if GOOGLE_CLIENT_ID is None or GOOGLE_CLIENT_SECRET is None:
    raise Exception('Missing env variables')

config_data = {'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID, 'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET}

starlette_config = Config(environ=config_data)

oauth = OAuth(starlette_config)
SCOPE = 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/userinfo.profile openid'

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': SCOPE},
)


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id}

    expires = datetime.now(UTC) + expires_delta

    encode.update({"exp": expires})

    return jwt.encode(encode, os.getenv("SECRET_KEY"), algorithm=ALGORITHM)


def create_refresh_token(username: str, user_id: int, expires_delta: timedelta):
    return create_access_token(username, user_id, expires_delta)


def decode_token(token):
    return jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=ALGORITHM)


def get_current_user(token: Annotated[str, Depends(oauth_bearer)]):
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=ALGORITHM)
        username: str = payload.get("sub")
        user_id: int = payload.get("id")

        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user.")


def token_expired(token: Annotated[str, Depends(oauth_bearer)]):
    try:
        payload = decode_token(token)
        if not datetime.fromtimestamp(payload.get('exp'), ) > datetime.now(UTC):
            return True
        return False

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user.")


user_dependency = Annotated[dict, Depends(get_current_user)]
