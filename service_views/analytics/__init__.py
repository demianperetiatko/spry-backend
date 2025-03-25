from .team import router as team_router
from .personal import router as personal_router
from fastapi import APIRouter

router = APIRouter()

router.include_router(team_router, tags=["analytics_team"])
router.include_router(personal_router, tags=["analytics_personal"])



