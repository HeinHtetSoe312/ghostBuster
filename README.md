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

## Notes
- Training data is synthetic; stop coordinates and routes are approximate. See ROADMAP.md for the NTA GTFS-Realtime plan.
- The UI loads Tailwind and the Inter font from CDNs, so the demo machine needs internet access (the API itself is fully local).
- Browser geolocation works on http://127.0.0.1 / localhost.
