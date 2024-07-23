import uuid
from typing import TypeVar, List

from models.repositories import BaseRepo
from models import User, Team, TeamMember

T = TypeVar("T")


class UserRepository(BaseRepo[User]):
    def __init__(self, session):
        super().__init__(session, User)

    def find_by_email(self, email: str) -> User:
        return self.session.query(User).filter(User.email == email).first()


class TeamRepository(BaseRepo[Team]):
    def __init__(self, session):
        super().__init__(session, Team)

    def find_by_create_user_id(self, user_id: int) -> Team:
        return self.session.query(Team).filter(Team.create_user_id == user_id).first()

    def find_by_team_member(self, team_id: str) -> List[TeamMember]:
        return self.session.query(TeamMember).filter(TeamMember.team_id == team_id).all()


class TeamMemberRepository(BaseRepo[TeamMember]):
    def __init__(self, session):
        super().__init__(session, TeamMember)
