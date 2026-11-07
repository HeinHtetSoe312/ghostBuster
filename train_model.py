#!/usr/bin/env python3
"""GhostBuster trainer: synthesizes a realistic transit history and exports the model.

A "ghost" event = a scheduled departure that never materialised on time
(cancelled, no vehicle, or severely late). Features: hour, day_of_week, heavy_rain.
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "ghost_predictor.joblib"
DATA_PATH = ROOT / "data" / "synthetic_history.csv"
FEATURES = ["hour", "day_of_week", "heavy_rain"]
MODEL_VERSION = "1.0.0"

BASE_RISK = 0.10
# Additive ghost-risk contribution per hour of day (0..23)
HOUR_EFFECT = np.array([
    0.14, 0.16, 0.16, 0.15, 0.12, 0.08, 0.05, 0.12, 0.16, 0.09, 0.02, 0.00,
    0.01, 0.01, 0.03, 0.06, 0.12, 0.18, 0.16, 0.08, 0.04, 0.05, 0.08, 0.11,
])
# Relative scheduled-trip volume per hour (sampling weights)
HOUR_VOLUME = np.array([
    1.0, 1.0, 0.5, 0.5, 0.5, 1.0, 3.0, 6.0, 8.0, 6.0, 5.0, 5.0,
    5.0, 5.0, 5.0, 6.0, 8.0, 9.0, 8.0, 6.0, 4.0, 3.0, 2.0, 1.5,
])
PEAK_HOURS = [7, 8, 16, 17, 18]
DOW_WEIGHTS = np.array([0.16, 0.16, 0.16, 0.16, 0.16, 0.12, 0.08])  # Mon..Sun
RAIN_PROBABILITY = 0.12


def true_ghost_probability(hour: np.ndarray, dow: np.ndarray, rain: np.ndarray) -> np.ndarray:
    """Ground-truth data-generating process (vectorised)."""
    weekday = dow <= 4
    day_scale = np.where(weekday, 1.0, np.where(dow == 5, 0.6, 0.5))
    day_offset = np.select([dow == 4, dow == 5, dow == 6], [0.02, 0.03, 0.08], default=0.0)
    peak = np.isin(hour, PEAK_HOURS) & weekday
    rain_effect = rain * (0.10 + 0.14 * peak.astype(float))
    p = BASE_RISK + HOUR_EFFECT[hour] * day_scale + day_offset + rain_effect
    return np.clip(p, 0.02, 0.92)


def generate_dataset(n_samples: int, rng: np.random.Generator) -> pd.DataFrame:
    hour = rng.choice(24, size=n_samples, p=HOUR_VOLUME / HOUR_VOLUME.sum())
    dow = rng.choice(7, size=n_samples, p=DOW_WEIGHTS)
    rain = (rng.random(n_samples) < RAIN_PROBABILITY).astype(int)
    p = true_ghost_probability(hour, dow, rain) + rng.normal(0.0, 0.02, size=n_samples)
    p = np.clip(p, 0.01, 0.95)
    ghosted = (rng.random(n_samples) < p).astype(int)
    return pd.DataFrame(
        {"hour": hour, "day_of_week": dow, "heavy_rain": rain, "ghosted": ghosted}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GhostBuster predictor.")
    parser.add_argument("--samples", type=int, default=150_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    df = generate_dataset(args.samples, rng)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    print(f"[data]  {len(df):,} rows | ghost rate {df['ghosted'].mean():.3f} -> {DATA_PATH}")

    X, y = df[FEATURES], df["ghosted"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=args.seed, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=25,
        n_jobs=-1,
        random_state=args.seed,
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, list(model.classes_).index(1)]
    auc = roc_auc_score(y_test, proba)
    brier = brier_score_loss(y_test, proba)

    # Calibration check against the known generating process over the full feature grid
    grid = pd.DataFrame(
        list(itertools.product(range(24), range(7), (0, 1))), columns=FEATURES
    )
    pred = model.predict_proba(grid)[:, list(model.classes_).index(1)]
    truth = true_ghost_probability(
        grid["hour"].to_numpy(), grid["day_of_week"].to_numpy(), grid["heavy_rain"].to_numpy()
    )
    mae = float(np.mean(np.abs(pred - truth)))
    print(f"[eval]  ROC-AUC {auc:.4f} | Brier {brier:.4f} | grid MAE vs truth {mae:.4f}")

    artifact = {
        "model": model,
        "feature_names": FEATURES,
        "metadata": {
            "version": MODEL_VERSION,
            "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_samples": int(len(df)),
            "n_estimators": int(model.n_estimators),
            "roc_auc": round(float(auc), 4),
            "brier": round(float(brier), 4),
            "grid_mae": round(mae, 4),
            "data_source": "synthetic",
        },
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH, compress=3)
    print(f"[model] exported -> {MODEL_PATH}")

    print("\n[demo]  Stop Credit Score (300-850) for key scenarios (no stop bias):")
    scenarios = [
        ("Tue 08:00 dry", 8, 1, 0),
        ("Thu 17:00 dry", 17, 3, 0),
        ("Thu 17:00 HEAVY RAIN", 17, 3, 1),
        ("Sat 01:00 dry", 1, 5, 0),
        ("Sun 11:00 dry", 11, 6, 0),
        ("Wed 11:00 dry", 11, 2, 0),
    ]
    for label, h, d, r in scenarios:
        p = model.predict_proba(pd.DataFrame([[h, d, r]], columns=FEATURES))[0, 1]
        print(f"        {label:<22} ghost p={p:.2f}  score={round(300 + 550 * (1 - p))}")


if __name__ == "__main__":
    main()
