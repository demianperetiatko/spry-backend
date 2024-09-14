from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from service_views import (
    team as team_view,
    agenda as agenda_view,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(team_view.router, tags=["team"])
app.include_router(agenda_view.router, tags=["agenda"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
