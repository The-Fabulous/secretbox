"""Assemble the API and website into one service."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend import analytics, auth, chat, menus
from backend.config import CORS_ORIGINS, FRONTEND_DIST
from backend.database import init_db


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="SecretBox Cafe Menu API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (auth.router, chat.router, menus.router, analytics.router):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def website():
    return RedirectResponse("/secretbox/")


if (FRONTEND_DIST / "index.html").is_file():
    app.mount("/secretbox", StaticFiles(directory=FRONTEND_DIST, html=True), name="website")
