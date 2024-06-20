from fastapi import Header, HTTPException, Depends

from sqlalchemy.orm import Session

from models import get_db
from models.repositories.user_repository import UserRepository


def get_user(token: str = Header(None, convert_underscores=False), db: Session = Depends(get_db)):
    user_repository = UserRepository(db)
    try:
        user = user_repository.find_by_email(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid auth token")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid auth token")
