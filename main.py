import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from service_views import (
    auth as auth_view,
    profile as profile_view,
    organization as organization_view,
    analytics as analytics_view,
    agenda as agenda_view,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.spryplan.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
SECRET_KEY = os.getenv("SECRET_KEY")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(auth_view.router, tags=["auth"])
app.include_router(profile_view.router, tags=["profile"])
app.include_router(organization_view.router)
app.include_router(agenda_view.router, tags=["agenda"])
app.include_router(analytics_view.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
