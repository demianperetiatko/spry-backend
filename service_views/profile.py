from fastapi import Depends, APIRouter, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, User
from models.repositories.user_repository import UserRepository

from utils.services import authenticated_user

router = APIRouter()


@router.get("/profile/")
def get_profile(user: User = Depends(authenticated_user)):
    return user


@router.put("/profile/")
def update_profile(
        name: str | None = Form(default=None),
        photo_file: UploadFile | None = File(None),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    user_repository = UserRepository(db)
    user.name = name
    updated_user = user_repository.update(user)
