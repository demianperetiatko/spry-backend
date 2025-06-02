from typing import TypeVar, List

from models.repositories import BaseRepo
from models import AgendaBeta

T = TypeVar("T")


class AgendaBetaRepository(BaseRepo[AgendaBeta]):
    def __init__(self, session):
        super().__init__(session, AgendaBeta)

    def find_by_event_id(self, event_id, member_id) -> AgendaBeta:
        return (
            self.session.query(AgendaBeta)
            .filter(AgendaBeta.event_id == event_id)
            .filter(AgendaBeta.member_id == member_id)
            .first()
        )
