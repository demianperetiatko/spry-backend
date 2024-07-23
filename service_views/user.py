import uuid

from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy.orm import Session

from models import get_db, User, Team, TeamMember
from models.repositories.user_repository import UserRepository, TeamRepository, TeamMemberRepository
from utils.auth import get_user

router = APIRouter()


class EmailRequest(BaseModel):
    email: str


@router.post("/user/invite/")
async def user_invite(email_request: EmailRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    team_repository = TeamRepository(db)
    team_member_repository = TeamMemberRepository(db)
    print(user.id)
    team = team_repository.find_by_create_user_id(user.id)
    if not team:
        team = Team(create_user_id=user.id)
        team_repository.create(team)

    team_member = TeamMember(
        team_id=team.id,
        email=email_request.email,
        added_by_id=user.id
    )
    team_member_repository.create(team_member)
