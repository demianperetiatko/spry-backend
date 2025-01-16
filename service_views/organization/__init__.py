from .member import router as member_router
from .team import router as team_router

from fastapi import APIRouter

router = APIRouter()

router.include_router(member_router, tags=["member"])
router.include_router(team_router, tags=["team"])
