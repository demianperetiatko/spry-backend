import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from src.core.bootstrap import compile_orm
from src.core.config import settings
from src.core.database.session import sessionmanager
from src.core.exceptions import NotFoundException, ServiceException
from src.modules.analytics.organization.router import router as analytics_organization_router
from src.modules.analytics.personal.router import router as analytics_personal_router
from src.modules.auth.router import router as auth_router
from src.modules.calendar.router import router as calendar_router
from src.modules.calendar.router import webhook_router as calendar_webhook_router
from src.modules.calendar.subscriber import setup_calendar_subscriber
from src.modules.home.router import router as home_router
from src.modules.invitation.router import router as invitation_router
from src.modules.organization.router import router as organization_router
from src.modules.organization_member.router import router as organization_member_router
from src.modules.organization_team.router import router as organization_team_router
from src.modules.user.router import router as user_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        compile_orm()
        setup_calendar_subscriber()
        yield
    finally:
        await sessionmanager.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message, "code": exc.code},
    )


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=404,
        content={"status": "error", "message": exc.message},
    )


if settings.SECRET_KEY:
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(organization_router)
app.include_router(organization_member_router)
app.include_router(organization_team_router)
app.include_router(invitation_router)
app.include_router(calendar_webhook_router)
app.include_router(calendar_router)
app.include_router(analytics_personal_router)
app.include_router(analytics_organization_router)
app.include_router(home_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
