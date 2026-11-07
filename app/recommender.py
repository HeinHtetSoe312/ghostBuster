from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app.config import Settings, settings
from app.ml_engine import GhostPredictor
from app.schemas import AlternativeOut, ContextOut, ScoreResponse, StopOut
from app.stops_registry import BusStop, StopRegistry
from app.time_context import DAY_NAMES


@dataclass(frozen=True)
class Assessment:
    probability: float
    score: int
    tier: str
    tier_label: str


def stop_out(stop: BusStop) -> StopOut:
    return StopOut(
        stop_id=stop.stop_id,
        name=stop.name,
        city=stop.city,
        lat=stop.lat,
        lon=stop.lon,
        routes=list(stop.routes),
    )


class Recommender:
    """Combines the ML engine and stop registry into scored answers + alternatives."""

    def __init__(
        self, predictor: GhostPredictor, registry: StopRegistry, cfg: Settings = settings
    ) -> None:
        self.predictor = predictor
        self.registry = registry
        self.cfg = cfg

    def assess(self, stop: BusStop, when: datetime, heavy_rain: bool) -> Assessment:
        p = self.predictor.ghost_probability(
            when.hour, when.weekday(), heavy_rain, stop.ghost_bias
        )
        score = self.predictor.score_from_probability(p)
        tier, label = self.predictor.tier_for(score)
        return Assessment(p, score, tier, label)

    def _alternatives(
        self,
        lat: float,
        lon: float,
        current_stop: BusStop,
        current: Assessment,
        when: datetime,
        heavy_rain: bool,
    ) -> List[AlternativeOut]:
        ranked: List[Tuple[float, AlternativeOut]] = []
        for stop, dist in self.registry.within_radius(
            lat, lon, self.cfg.alt_search_radius_m, exclude_id=current_stop.stop_id
        ):
            walk_min = dist * self.cfg.walk_detour_factor / self.cfg.walk_speed_m_per_min
            arrival = when + timedelta(minutes=walk_min)  # score at the time you'd arrive
            alt = self.assess(stop, arrival, heavy_rain)
            gain = alt.score - current.score
            if gain < self.cfg.min_alt_gain:
                continue
            utility = alt.score - walk_min * self.cfg.walk_penalty_per_min
            ranked.append(
                (
                    utility,
                    AlternativeOut(
                        stop=stop_out(stop),
                        distance_m=int(round(dist)),
                        walk_minutes=max(1, int(math.ceil(walk_min))),
                        score=alt.score,
                        tier=alt.tier,
                        tier_label=alt.tier_label,
                        ghost_probability=round(alt.probability, 4),
                        score_gain=gain,
                    ),
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [alt for _, alt in ranked[: self.cfg.max_alternatives]]

    @staticmethod
    def _advice(current: Assessment, alternatives: List[AlternativeOut]) -> str:
        if current.tier == "prime":
            return "Strong odds your bus shows up. A normal buffer is fine."
        if current.tier == "near_prime":
            return "Moderate ghost risk. Leave a 10-15 minute buffer and keep a backup in mind."
        if alternatives:
            best = alternatives[0]
            return (
                f"High ghost risk here. {best.stop.name} is a {best.walk_minutes}-minute walk "
                f"and scores {best.score} (+{best.score_gain})."
            )
        return "High ghost risk and no clearly better stop within walking distance. Plan a backup."

    def evaluate(
        self,
        lat: float,
        lon: float,
        when: datetime,
        simulated: bool,
        heavy_rain: bool,
    ) -> Optional[ScoreResponse]:
        match = self.registry.nearest(lat, lon, self.cfg.max_match_radius_m)
        if match is None:
            return None
        stop, dist = match
        current = self.assess(stop, when, heavy_rain)
        triggered = current.tier == "subprime"
        alternatives = (
            self._alternatives(lat, lon, stop, current, when, heavy_rain) if triggered else []
        )
        return ScoreResponse(
            stop=stop_out(stop),
            distance_m=round(dist, 1),
            score=current.score,
            tier=current.tier,
            tier_label=current.tier_label,
            ghost_probability=round(current.probability, 4),
            advice=self._advice(current, alternatives),
            context=ContextOut(
                hour=when.hour,
                day_of_week=when.weekday(),
                day_name=DAY_NAMES[when.weekday()],
                heavy_rain=heavy_rain,
                local_time_label=when.strftime("%a %H:%M"),
                simulated=simulated,
            ),
            alternatives_triggered=triggered,
            alternatives=alternatives,
            engine_version=self.predictor.version,
        )
