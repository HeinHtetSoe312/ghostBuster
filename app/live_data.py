from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


@dataclass(frozen=True)
class WeatherObservation:
    heavy_rain: bool
    precipitation_mm: float | None
    observed_at: str | None
    source: str
    error: str | None = None


class WeatherClient:
    """Reads current precipitation from Open-Meteo's public forecast API."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def current(self, lat: float, lon: float) -> WeatherObservation:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.6f}&longitude={lon:.6f}"
            "&current=precipitation,rain,showers&timezone=UTC"
        )
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "GhostBuster/0.1"})
        try:
            tls_context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(request, timeout=self.timeout_seconds, context=tls_context) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return WeatherObservation(
                heavy_rain=False,
                precipitation_mm=None,
                observed_at=None,
                source="unavailable",
                error=f"Live weather unavailable: {exc}",
            )

        current = payload.get("current")
        if not isinstance(current, dict):
            return WeatherObservation(
                heavy_rain=False,
                precipitation_mm=None,
                observed_at=None,
                source="unavailable",
                error="Live weather returned no current observation.",
            )
        try:
            precipitation = float(current["precipitation"])
            observed_at = str(current["time"])
        except (KeyError, TypeError, ValueError):
            return WeatherObservation(
                heavy_rain=False,
                precipitation_mm=None,
                observed_at=None,
                source="unavailable",
                error="Live weather returned an invalid current observation.",
            )
        return WeatherObservation(
            heavy_rain=precipitation >= 2.5,
            precipitation_mm=round(precipitation, 2),
            observed_at=observed_at,
            source="open-meteo",
        )
