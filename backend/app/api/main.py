"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    yield


app = FastAPI(
    title="JustePrix Immo API",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────

from app.api.routes.listings import router as listings_router  # noqa: E402
from app.api.routes.cities import router as cities_router  # noqa: E402

app.include_router(listings_router)
app.include_router(cities_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
