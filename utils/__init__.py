from sqlalchemy.orm import Session
from models.repositories.user_repository import UserRepository


def get_user_profile(email: str, db: Session):
    name = None
    photo_url = None
    user_repository = UserRepository(db)
    user = user_repository.find_by_email(email)
    if user:
        name = user.name
        photo_url = user.photo_url

    return {
        "name": name,
        "email": email,
        "photo_url": photo_url
    }
