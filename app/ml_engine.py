from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import pandas as pd

from app.config import Settings, settings

EXPECTED_FEATURES = ("hour", "day_of_week", "heavy_rain")

TIER_LABELS = {
    "prime": "Prime - Reliable",
    "near_prime": "Near-Prime - Some Risk",
    "subprime": "Subprime - Likely Ghost",
}


class GhostPredictor:
    """Loads the Joblib RandomForest and converts ghost probability to a 300-850 score."""

    def __init__(self, model_path: Path, cfg: Settings = settings) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model artifact not found at {model_path}. Run `python train_model.py` first."
            )
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = tuple(artifact["feature_names"])
        if self.feature_names != EXPECTED_FEATURES:
            raise ValueError(
                f"Model feature mismatch: expected {EXPECTED_FEATURES}, got {self.feature_names}"
            )
        self.metadata: Dict[str, Any] = dict(artifact.get("metadata", {}))
        self.cfg = cfg
        self.model.set_params(n_jobs=1)  # single-row inference: avoid thread overhead
        self._positive_idx = list(self.model.classes_).index(1)
        self._cache: Dict[Tuple[int, int, int], float] = {}

    @property
    def version(self) -> str:
        return str(self.metadata.get("version", "unknown"))

    def raw_probability(self, hour: int, day_of_week: int, heavy_rain: bool) -> float:
        key = (int(hour), int(day_of_week), int(bool(heavy_rain)))
        cached = self._cache.get(key)
        if cached is None:
            frame = pd.DataFrame([list(key)], columns=list(self.feature_names))
            cached = float(self.model.predict_proba(frame)[0, self._positive_idx])
            self._cache[key] = cached
        return cached

    def ghost_probability(
        self, hour: int, day_of_week: int, heavy_rain: bool, stop_bias: float = 0.0
    ) -> float:
        """Model probability plus a per-stop prior offset, clipped to [0.01, 0.99]."""
        p = self.raw_probability(hour, day_of_week, heavy_rain) + stop_bias
        return min(0.99, max(0.01, p))

    def score_from_probability(self, ghost_probability: float) -> int:
        span = self.cfg.score_max - self.cfg.score_min
        score = self.cfg.score_min + span * (1.0 - ghost_probability)
        return int(round(min(self.cfg.score_max, max(self.cfg.score_min, score))))

    def tier_for(self, score: int) -> Tuple[str, str]:
        if score >= self.cfg.prime_threshold:
            key = "prime"
        elif score >= self.cfg.near_prime_threshold:
            key = "near_prime"
        else:
            key = "subprime"
        return key, TIER_LABELS[key]
