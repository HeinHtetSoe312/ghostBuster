from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.ml_engine import GhostPredictor
from app.recommender import Recommender
from app.routers.api import router as api_router
from app.stops_registry import STOPS, StopRegistry

logger = logging.getLogger("ghostbuster")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.model_path.exists():
        raise RuntimeError(
            f"Model artifact missing at {settings.model_path}. Run `python train_model.py` first."
        )
    predictor = GhostPredictor(settings.model_path, settings)
    registry = StopRegistry(STOPS)
    app.state.recommender = Recommender(predictor, registry, settings)
    logger.info(
        "GhostBuster ready: model v%s, %d stops indexed", predictor.version, len(registry)
    )
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.version,
    description="Predictive transit reliability: Stop Credit Scores for Irish bus stops.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mounted last so /api/* and /docs take precedence; serves frontend/index.html at "/".
app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
