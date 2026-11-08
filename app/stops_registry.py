from __future__ import annotations

import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class BusStop:
    stop_id: str
    name: str
    city: str
    lat: float
    lon: float
    routes: Tuple[str, ...]
    # Stop-level prior on ghost probability (negative = more reliable than the
    # city baseline, e.g. dispatch hubs; positive = exposed/congested corridors).
    ghost_bias: float


# Seed registry: approximate coordinates and illustrative route numbers.
# Replace with the NTA static GTFS import (see ROADMAP.md).
STOPS: Tuple[BusStop, ...] = (
    # --- Cork ---
    BusStop("CK-001", "Patrick Street", "Cork", 51.8988, -8.4715, ("201", "202", "205", "208", "220"), 0.05),
    BusStop("CK-002", "Grand Parade", "Cork", 51.8978, -8.4764, ("201", "205", "208", "214"), 0.01),
    BusStop("CK-003", "Parnell Place Bus Station", "Cork", 51.8996, -8.4658, ("220", "226", "235", "240"), -0.15),
    BusStop("CK-004", "Merchant's Quay", "Cork", 51.9006, -8.4738, ("202", "209", "214"), -0.08),
    BusStop("CK-005", "Anglesea Street", "Cork", 51.8972, -8.4695, ("205", "208"), -0.02),
    BusStop("CK-006", "South Mall", "Cork", 51.8962, -8.4742, ("201", "202"), 0.00),
    BusStop("CK-007", "Washington Street", "Cork", 51.8972, -8.4808, ("208", "214", "220"), 0.04),
    BusStop("CK-008", "Albert Quay", "Cork", 51.8958, -8.4648, ("202", "220"), -0.05),
    BusStop("CK-009", "Shandon Street", "Cork", 51.9040, -8.4783, ("209", "214"), 0.07),
    BusStop("CK-010", "Kent Station", "Cork", 51.9007, -8.4580, ("202", "220", "226"), -0.10),
    BusStop("CK-011", "UCC Main Gate", "Cork", 51.8935, -8.4917, ("208", "214"), 0.03),
    BusStop("CK-012", "CUH Wilton", "Cork", 51.8843, -8.5086, ("208", "214"), 0.04),
    BusStop("CK-013", "Mahon Point", "Cork", 51.8846, -8.3980, ("202", "220"), 0.06),
    BusStop("CK-014", "Lower Glanmire Road", "Cork", 51.9010, -8.4620, ("226", "240"), 0.05),
    # --- Dublin ---
    BusStop("DB-001", "O'Connell Street", "Dublin", 53.3498, -6.2603, ("1", "16", "41"), 0.04),
    BusStop("DB-002", "Connolly Station", "Dublin", 53.3510, -6.2500, ("1", "16"), -0.08),
    BusStop("DB-003", "Dame Street", "Dublin", 53.3440, -6.2650, ("9", "14", "15"), 0.02),
    # --- Galway ---
    BusStop("GY-001", "Eyre Square", "Galway", 53.2744, -9.0490, ("401", "402", "404"), 0.00),
)


def load_stops(path: Path) -> Tuple[BusStop, ...]:
    """Load the official TFI GTFS stop snapshot, falling back to the demo seed."""
    if not path.exists():
        return STOPS
    with path.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    stops = tuple(
        BusStop(
            stop_id=str(row["stop_id"]),
            name=str(row["name"]),
            city=str(row.get("city") or "Ireland"),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            routes=tuple(str(route) for route in row.get("routes", [])),
            ghost_bias=float(row.get("ghost_bias", 0.0)),
        )
        for row in rows
    )
    if not stops:
        raise ValueError(f"GTFS stop snapshot is empty: {path}")
    return stops


class StopRegistry:
    """In-memory stop database with a latitude/longitude grid index."""

    def __init__(self, stops: Iterable[BusStop]) -> None:
        self._stops: List[BusStop] = list(stops)
        self._by_id: Dict[str, BusStop] = {s.stop_id: s for s in self._stops}
        self._grid: Dict[Tuple[int, int], List[BusStop]] = {}
        for stop in self._stops:
            self._grid.setdefault(self._cell(stop.lat, stop.lon), []).append(stop)
        if len(self._by_id) != len(self._stops):
            raise ValueError("Duplicate stop_id detected in registry.")

    @staticmethod
    def _cell(lat: float, lon: float) -> Tuple[int, int]:
        return int(lat * 100), int(lon * 100)

    def _candidates(self, lat: float, lon: float, radius_m: float) -> Iterable[BusStop]:
        lat_delta = radius_m / 111_320
        lon_delta = radius_m / (111_320 * max(0.1, math.cos(math.radians(lat))))
        min_lat, max_lat = self._cell(lat - lat_delta, lon)[0], self._cell(lat + lat_delta, lon)[0]
        min_lon, max_lon = self._cell(lat, lon - lon_delta)[1], self._cell(lat, lon + lon_delta)[1]
        for lat_cell in range(min_lat, max_lat + 1):
            for lon_cell in range(min_lon, max_lon + 1):
                yield from self._grid.get((lat_cell, lon_cell), ())

    def __len__(self) -> int:
        return len(self._stops)

    def all(self) -> List[BusStop]:
        return list(self._stops)

    def get(self, stop_id: str) -> Optional[BusStop]:
        return self._by_id.get(stop_id)

    def nearest(
        self, lat: float, lon: float, max_radius_m: float
    ) -> Optional[Tuple[BusStop, float]]:
        best: Optional[Tuple[BusStop, float]] = None
        for stop in self._candidates(lat, lon, max_radius_m):
            d = haversine_m(lat, lon, stop.lat, stop.lon)
            if best is None or d < best[1]:
                best = (stop, d)
        if best is None or best[1] > max_radius_m:
            return None
        return best

    def within_radius(
        self, lat: float, lon: float, radius_m: float, exclude_id: Optional[str] = None
    ) -> List[Tuple[BusStop, float]]:
        hits: List[Tuple[BusStop, float]] = []
        for stop in self._candidates(lat, lon, radius_m):
            if stop.stop_id == exclude_id:
                continue
            d = haversine_m(lat, lon, stop.lat, stop.lon)
            if d <= radius_m:
                hits.append((stop, d))
        hits.sort(key=lambda item: item[1])
        return hits
