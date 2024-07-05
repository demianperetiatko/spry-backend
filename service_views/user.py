import uuid

from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy.orm import Session

from models import get_db, User
from models.repositories.user_repository import UserRepository
from utils.auth import get_user

router = APIRouter()


def generate_unique_token():
    return uuid.uuid4().hex


class EmailRequest(BaseModel):
    email: str


@router.post("/user/invite/")
async def user_invite(email_request: EmailRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    user_repository = UserRepository(db)

    new_user = user_repository.find_by_email(email_request.email)
    if new_user:
        raise HTTPException(status_code=400, detail="New user already exists")

    invite_token = generate_unique_token()
    new_user = User(email=email_request.email)
    user_repository.create(new_user)
    return


