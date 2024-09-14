import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import AgendaItem

T = TypeVar("T")


class AgendaItemRepository(BaseRepo[AgendaItem]):
    def __init__(self, session):
        super().__init__(session, AgendaItem)

    def find_by_create_user_id(self, create_user_id: int) -> List[AgendaItem]:
        return self.session.query(AgendaItem).filter_by(create_user_id=create_user_id).all()