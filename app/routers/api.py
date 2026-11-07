from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import settings
from app.recommender import Recommender, stop_out
from app.schemas import HealthResponse, ScoreResponse, StopOut
from app.time_context import resolve_when

router = APIRouter(prefix="/api", tags=["ghostbuster"])


def get_recommender(request: Request) -> Recommender:
    return request.app.state.recommender


@router.get("/health", response_model=HealthResponse)
def health(svc: Recommender = Depends(get_recommender)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_version=settings.version,
        stop_count=len(svc.registry),
        ml=svc.predictor.metadata,
    )


@router.get("/stops", response_model=List[StopOut])
def list_stops(svc: Recommender = Depends(get_recommender)) -> List[StopOut]:
    return [stop_out(s) for s in svc.registry.all()]


@router.get("/score", response_model=ScoreResponse)
def score(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (WGS84)"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude (WGS84)"),
    heavy_rain: bool = Query(False, description="Heavy rain flag"),
    hour: Optional[int] = Query(None, ge=0, le=23, description="Simulated hour (0-23)"),
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="Simulated weekday (Mon=0)"),
    svc: Recommender = Depends(get_recommender),
) -> ScoreResponse:
    when, simulated = resolve_when(settings.timezone, hour, day_of_week)
    result = svc.evaluate(lat, lon, when, simulated, heavy_rain)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No covered bus stops within "
                f"{int(settings.max_match_radius_m)} m of this location. "
                "GhostBuster currently covers Cork, Dublin and Galway city centres."
            ),
        )
    return result
