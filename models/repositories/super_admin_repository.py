from typing import TypeVar, List

from models.repositories import BaseRepo
from models import SuperAdmin

T = TypeVar("T")


class SuperAdminRepository(BaseRepo[SuperAdmin]):
    def __init__(self, session):
        super().__init__(session, SuperAdmin)

    def find_by_email(self, email: str) -> SuperAdmin:
        return self.session.query(SuperAdmin).filter(SuperAdmin.email == email).first()
