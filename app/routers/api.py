from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import settings
from app.live_data import WeatherClient
from app.recommender import Recommender, stop_out
from app.schemas import HealthResponse, ScoreResponse, StopOut
from app.time_context import resolve_when

router = APIRouter(prefix="/api", tags=["ghostbuster"])


def get_recommender(request: Request) -> Recommender:
    return request.app.state.recommender


def get_weather(request: Request) -> WeatherClient:
    return request.app.state.weather


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
    heavy_rain: Optional[bool] = Query(
        None, description="Override live weather detection (omit to use live weather)"
    ),
    hour: Optional[int] = Query(None, ge=0, le=23, description="Simulated hour (0-23)"),
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="Simulated weekday (Mon=0)"),
    svc: Recommender = Depends(get_recommender),
    weather: WeatherClient = Depends(get_weather),
) -> ScoreResponse:
    when, simulated = resolve_when(settings.timezone, hour, day_of_week)
    live_weather = weather.current(lat, lon)
    rain = heavy_rain if heavy_rain is not None else live_weather.heavy_rain
    weather_source = "manual-override" if heavy_rain is not None else live_weather.source
    result = svc.evaluate(
        lat,
        lon,
        when,
        simulated,
        rain,
        weather_source=weather_source,
        weather_error=live_weather.error,
        precipitation_mm=live_weather.precipitation_mm,
        weather_observed_at=live_weather.observed_at,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No covered bus stops within "
                f"{int(settings.max_match_radius_m)} m of this location. "
                "GhostBuster currently uses the official TFI stop snapshot. Try a location closer to a mapped stop."
            ),
        )
    return result
