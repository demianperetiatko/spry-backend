from .team import router as team_router

from fastapi import APIRouter

router = APIRouter()

router.include_router(team_router, tags=["analytics_team"])



