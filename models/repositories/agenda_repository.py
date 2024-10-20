import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import AgendaTemplate

T = TypeVar("T")


class AgendaTemplateRepository(BaseRepo[AgendaTemplate]):
    def __init__(self, session):
        super().__init__(session, AgendaTemplate)

    def find_by_create_user_id(self, create_user_id: int) -> List[AgendaTemplate]:
        return self.session.query(AgendaTemplate).filter_by(create_user_id=create_user_id).all()

    def find_by_id_and_user_id(self, id_: int, user_id: int) -> List[AgendaTemplate]:
        return self.session.query(AgendaTemplate).filter_by(id=id_, create_user_id=user_id).all()
