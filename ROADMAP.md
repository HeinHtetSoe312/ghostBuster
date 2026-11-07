# GhostBuster Roadmap: From Scaffold to Live NTA Telemetry

## Where we are (v0.1 - Scaffold MVP)
- RandomForest trained on **synthetic** history (hour, weekday, heavy rain), running on CPU via Joblib.
- Seed registry of 18 stops (approximate coordinates, illustrative routes) with a per-stop prior (`ghost_bias`).
- Stop Credit Score = 300 + 550 x (1 - P(ghost)); tiers: Prime >= 700, Near-Prime 550-699, Subprime < 550.
- Alternative stops are re-scored at *arrival time* (now + walking time) and ranked by score minus a walking penalty.

## Phase 1 - Real static network (week 1-2)
- Import the NTA / Transport for Ireland **static GTFS** feed (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`).
- Replace `STOPS` with a loader writing to SQLite/PostGIS; add a spatial index (R-tree or `ST_DWithin`).
- Keep `StopRegistry`'s interface (`nearest`, `within_radius`) so the recommender is untouched.

## Phase 2 - GTFS-Realtime ingestion (week 2-4)
- Poll the NTA GTFS-R feeds (TripUpdates, Vehicle Positions, Service Alerts) via the NTA developer portal.
  Verify current endpoint paths, API-key header, rate limits and licence terms in the portal docs before building.
- Parse protobuf with `gtfs-realtime-bindings`; persist every observation with a timestamp.

```python
# ingest/gtfsr_poller.py (sketch)
import httpx
from google.transit import gtfs_realtime_pb2

FEED_URL = "<NTA GTFS-R TripUpdates endpoint>"   # from the NTA portal
HEADERS = {"x-api-key": "<KEY_FROM_ENV>"}        # confirm header name in portal docs

def poll_once(client: httpx.Client):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(client.get(FEED_URL, headers=HEADERS, timeout=15).content)
    for ent in feed.entity:
        if ent.HasField("trip_update"):
            tu = ent.trip_update
            for stu in tu.stop_time_update:
                yield (tu.trip.trip_id, stu.stop_id, stu.departure.delay,
                       tu.trip.schedule_relationship, feed.header.timestamp)

# run every 30-60 s from a worker (APScheduler / Celery beat / systemd timer)
```

## Phase 3 - Define "ghost" from ground truth (week 3-5)
A scheduled stop-time is a **ghost** if any of:
1. `schedule_relationship` is CANCELED or SKIPPED at that stop, or
2. no real-time update/vehicle ever matched the trip within a grace window, or
3. observed departure delay exceeds a threshold (e.g. > 10 min).

Join with scheduled `stop_times` -> training rows `(stop_id, route_id, hour, dow, rain, ghosted)`.

## Phase 4 - Better model (week 4-8)
- Add features: route, stop_id (or learned embedding), headway, month/holiday/school-term flag, event calendar, upstream-stop delay.
- Replace the manual rain toggle with Met Eireann / Open-Meteo hourly forecasts (precipitation mm/h threshold).
- Replace the hand-set `ghost_bias` with learned stop effects; evaluate with time-based splits and calibration curves
  (`CalibratedClassifierCV`) so the 300-850 score maps to honest probabilities.
- Model registry + nightly retrain; keep the Joblib artifact contract (`model`, `feature_names`, `metadata`).

## Phase 5 - Product & scale (week 6-12)
- Real multimodal routing (OpenTripPlanner / Valhalla) to replace the straight-line walk heuristic.
- Push alerts ("Your 17:40 from Patrick St is subprime - leave via Parnell Place at 17:28").
- Redis cache for scores per (stop, hour, dow, rain); horizontal scale behind a load balancer.
- PWA / React Native client, saved commutes, accessibility.
- Observability: Prometheus metrics, drift monitoring on predicted vs observed ghost rate per stop.

## Business model hooks
- B2C freemium (commute alerts), B2B (employers, universities, hospital rosters), B2G (NTA / local-authority reliability dashboards, open-data partnership).
