from fastapi import APIRouter

from .personal import router as personal_router
from .team import router as team_router

router = APIRouter()

router.include_router(team_router, tags=["analytics_team"])
router.include_router(personal_router, tags=["analytics_personal"])
