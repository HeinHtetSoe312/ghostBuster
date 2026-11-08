# GhostBuster

Predictive transit reliability for Irish commuters. Every bus stop gets a **Stop Credit Score (300-850)** from a
RandomForest model (hour, weekday, heavy rain). Subprime stops trigger walkable alternative recommendations.

## Run (model is pre-trained and included)
    python -m venv .venv
    # macOS/Linux: source .venv/bin/activate     Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Or use `run.sh` (macOS/Linux) / `run.bat` (Windows), which do all of the above.

Open http://127.0.0.1:8000 (UI) and http://127.0.0.1:8000/docs (API docs).

Optional: `python train_model.py` regenerates the data and model.

## Stage demo
Flip **Stage Demo Mode Override** (or press **D**). Coordinates lock to Patrick Street, Cork (51.8988, -8.4715),
GPS is bypassed, and Thu 17:00 + heavy rain is preloaded: Patrick Street scores ~545 (subprime/red) with
amber alternatives (Parnell Place, Merchant's Quay, Anglesea Street).

## Live data
- Browser GPS is used when permission is available; otherwise the UI uses an explicitly labelled approximate IP location.
- Every live score request uses the server's current `Europe/Dublin` time and queries Open-Meteo for current precipitation at the detected coordinates. The model's rain feature is therefore live by default; the rain checkbox is an explicit override.
- The RandomForest is a real scikit-learn model, but its training labels are synthetic. It cannot honestly claim learned real ghost-bus performance until observed GTFS-Realtime trip updates are collected and used for retraining. The API labels this in `/api/health`.
- Live GTFS-Realtime transit predictions require an NTA developer API key and a verified feed endpoint; the static stop registry is not live vehicle telemetry.

## Notes
- Stop coordinates and routes are loaded from the official TFI GTFS schedule snapshot in `data/gtfs_stops.json`.
- The included ML training history is still synthetic: GTFS schedule data does not contain observed ghost/cancellation outcomes. NTA GTFS-Realtime is free after developer registration and API-key setup.
- The UI loads Tailwind and the Inter font from CDNs, so the demo machine needs internet access (the API itself is fully local).
- Start the app with `run.bat` or `run.sh` and open http://127.0.0.1:8000; do not open `frontend/index.html` directly, because browsers block geolocation from `file:` pages.
- Browser geolocation starts cached and fresh high-accuracy requests in parallel. A cached fix is used immediately only when it is newer than 30 seconds and reports accuracy of 150 m or better; otherwise the fresh fix wins. Fixes less accurate than 300 m are rejected instead of being used to select a misleading nearby stop. If the device has no location provider, the UI falls back to an approximate network location and labels it clearly. For precise live GPS, check the browser's location permission and open the app at `http://127.0.0.1:8000` (or over HTTPS).
- Live scoring uses the official TFI stop snapshot across Ireland. If GPS succeeds outside the coverage area, the UI shows the detected coordinates instead of treating the location as unavailable.
