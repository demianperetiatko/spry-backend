import uuid

from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy.orm import Session

from models import get_db, User, Hierarchy
from models.repositories.user_repository import UserRepository, HierarchyRepository
from utils.auth import get_user

router = APIRouter()


def generate_unique_token():
    return uuid.uuid4().hex


class EmailRequest(BaseModel):
    email: str


@router.post("/user/invite/")
async def user_invite(email_request: EmailRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    hierarchy_repository = HierarchyRepository(db)
    new_user = user_repository.find_by_email(email_request.email)
    if new_user:
        raise HTTPException(status_code=400, detail="New user already exists")

    invite_token = generate_unique_token()
    new_user = User(email=email_request.email, invite_token=invite_token, status=User.STATUS_NEW)
    user_repository.create(new_user)

    hierarchy = Hierarchy(manager_id=user.id, employee_id=new_user.id)
    hierarchy_repository.create(hierarchy)
    return {"token": invite_token}


@router.get("/user/create/")
async def user_create(invite_token: str, db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    new_user = user_repository.find_by_invite_token(invite_token)
    if not new_user:
        raise HTTPException(status_code=400, detail="User already exists")
    return {"email": new_user.email}

class UserRequest(BaseModel):
    invite_token: str
    name: str

@router.post("/user/create/")
async def user_create(user_request: UserRequest, db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    new_user = user_repository.find_by_invite_token(user_request.invite_token)

    if not new_user:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user.name = user_request.name
    new_user.status = User.STATUS_ACTIVE

    user_repository.update(new_user)
