import uuid

from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy.orm import Session

from models import get_db, User, InvitedUser
from models.repositories.user_repository import UserRepository
from models.repositories.user_repository import InvitedUserRepository
from utils.auth import get_user

router = APIRouter()


def generate_unique_token():
    return uuid.uuid4().hex


class EmailRequest(BaseModel):
    email: str


@router.post("/user/invite/")
async def user_invite(email_request: EmailRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    invited_user_repository = InvitedUserRepository(db)


    new_user = User(email=email_request.email)
    invited_user = InvitedUser(
        user_id=new_user.id,
        added_by_id=user.id
    )

    user_repository.create(new_user)
    invited_user_repository.create(invited_user)


