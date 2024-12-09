import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from service_views import (
    team as team_view,
    agenda as agenda_view,
    auth as auth_view,
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
app.include_router(team_view.router, tags=["team"])
app.include_router(agenda_view.router, tags=["agenda"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
