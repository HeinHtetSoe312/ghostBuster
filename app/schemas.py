from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class StopOut(BaseModel):
    stop_id: str
    name: str
    city: str
    lat: float
    lon: float
    routes: List[str]


class ContextOut(BaseModel):
    hour: int
    day_of_week: int
    day_name: str
    heavy_rain: bool
    local_time_label: str
    simulated: bool
    weather_source: str
    weather_error: str | None = None
    precipitation_mm: float | None = None
    weather_observed_at: str | None = None


class AlternativeOut(BaseModel):
    stop: StopOut
    distance_m: int
    walk_minutes: int
    score: int
    tier: str
    tier_label: str
    ghost_probability: float
    score_gain: int


class ScoreResponse(BaseModel):
    stop: StopOut
    distance_m: float
    score: int
    tier: str
    tier_label: str
    ghost_probability: float
    advice: str
    context: ContextOut
    alternatives_triggered: bool
    alternatives: List[AlternativeOut]
    engine_version: str


class HealthResponse(BaseModel):
    status: str
    app_version: str
    stop_count: int
    ml: Dict[str, Any]
