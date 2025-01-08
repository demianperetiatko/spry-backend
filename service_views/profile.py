from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, User
from models.repositories.user_repository import UserRepository

from utils.services import authenticated_user

router = APIRouter()


@router.get("/profile/")
def get_profile(user: User = Depends(authenticated_user)):
    return user


class UserUpdateRequest(BaseModel):
    name: str | None = None


@router.put("/profile/")
def update_profile(
        update_request: UserUpdateRequest,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    user_repository = UserRepository(db)
    user.name = update_request.name
    updated_user = user_repository.update(user)
