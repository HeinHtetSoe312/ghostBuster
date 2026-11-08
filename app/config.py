from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str = "GhostBuster"
    version: str = "0.1.0"

    model_path: Path = BASE_DIR / "models" / "ghost_predictor.joblib"
    stops_path: Path = BASE_DIR / "data" / "gtfs_stops.json"
    frontend_dir: Path = BASE_DIR / "frontend"
    timezone: str = "Europe/Dublin"

    # Stop Credit Score scale and tier thresholds
    score_min: int = 300
    score_max: int = 850
    prime_threshold: int = 700        # >= 700  -> green
    near_prime_threshold: int = 550   # 550-699 -> amber, < 550 -> red (subprime)

    # Spatial matching
    max_match_radius_m: float = 2000.0
    alt_search_radius_m: float = 900.0

    # Alternative-route recommendation
    walk_speed_m_per_min: float = 80.0   # ~4.8 km/h
    walk_detour_factor: float = 1.25     # straight-line -> street-network approximation
    min_alt_gain: int = 30               # minimum score improvement to recommend
    walk_penalty_per_min: float = 6.0    # utility penalty per walking minute
    max_alternatives: int = 3

    cors_origins: tuple = ("*",)


settings = Settings()
