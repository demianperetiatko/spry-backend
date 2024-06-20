import uuid
from typing import TypeVar

from models.repositories import BaseRepo
from models import User, Hierarchy

T = TypeVar("T")


class UserRepository(BaseRepo[User]):
    def __init__(self, session):
        super().__init__(session, User)

    def find_by_id(self, user_id: int, status: str = User.STATUS_ACTIVE) -> User:
        return self.session.query(User).filter(User.id == user_id).filter(User.status == status).first()

    def find_by_email(self, email: str) -> User:
        return self.session.query(User).filter(User.email == email).first()

    def find_by_invite_token(self, invite_token: str, status: str = User.STATUS_NEW) -> User:
        return self.session.query(User).filter(User.invite_token == invite_token).filter(User.status == status).first()


class HierarchyRepository(BaseRepo[Hierarchy]):
    def __init__(self, session):
        super().__init__(session, Hierarchy)
