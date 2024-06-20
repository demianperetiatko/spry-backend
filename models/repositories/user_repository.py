import uuid
from typing import TypeVar

from models.repositories import BaseRepo
from models import User


T = TypeVar("T")


class UserRepository(BaseRepo[User]):
    def __init__(self, session):
        super().__init__(session, User)

    def find_by_email(self, email: str) -> User:
        return self.session.query(User).filter(User.email == email).first()

    def find_by_invite_token(self, invite_token: str) -> User:
        return self.session.query(User).filter(User.invite_token == invite_token).first()
