from fastapi import Header, HTTPException, Depends

from sqlalchemy.orm import Session

from .firebase import verify_firebase_token

from models import get_db, User
from models.repositories.user_repository import UserRepository


def get_user(token: str = Header(None, convert_underscores=False), db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    try:
        email = verify_firebase_token(token)
    except:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    user = user_repository.find_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    else:
        user = User(email=email)
        user_repository.create(user)
    return user