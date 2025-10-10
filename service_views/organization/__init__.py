from fastapi import APIRouter

from .member import router as member_router
from .routers.member import router as members_router
from .settings import router as settings_router
from .team import router as team_router

router = APIRouter()

router.include_router(member_router, tags=["member"])
router.include_router(team_router, tags=["team"])
router.include_router(settings_router, tags=["settings"])

router.include_router(members_router, tags=["members"])
