# TruckTrack HOS Trip Planner

TruckTrack turns a current location, pickup, drop-off, departure time, and current 70-hour cycle usage into an HGV route, a compliance-aware duty timeline, and printable FMCSA-style daily logs.

This project was built for a senior full-stack assessment. It deliberately keeps the product stateless and concentrates complexity in two places: normalizing live route data and producing a deterministic schedule that never plans driving beyond the supported property-carrier limits.

> TruckTrack is a planning aid, not a certified electronic logging device or legal advice.

## What it does

- Geocodes three user-entered locations.
- Requests an openrouteservice `driving-hgv` route in the order current → pickup → drop-off.
- Plans one-hour pickup and delivery stops and a 30-minute fuel stop every 1,000 miles.
- Enforces the 11-hour driving limit, 14-hour window, 30-minute interruption after 8 cumulative driving hours, 10-hour daily reset, 70-hour cycle limit, and a conservative 34-hour restart.
- Displays the route, stop markers, synchronized duty timeline, and a compact ELD strip.
- Produces one filled log sheet for every calendar day in the terminal timezone.
- Exports individual PNG logs, a ZIP of all PNG logs, or all logs through the browser’s print-to-PDF flow.
- Publishes interactive OpenAPI documentation from Django.

## Architecture

```text
React + TypeScript                    Django REST API
┌───────────────────────┐            ┌─────────────────────────┐
│ planning form         │  HTTPS     │ input validation        │
│ MapLibre + OpenFreeMap│───────────▶│ openrouteservice client │
│ route/timeline/log UI │◀───────────│ HOS scheduler           │
│ PNG/PDF exports       │   JSON     │ daily-log projection    │
└───────────────────────┘            └─────────────────────────┘
```

The frontend and backend are separate deployable projects in one repository. Django owns the openrouteservice key and all compliance calculations. React only renders the returned contract and creates local exports. There is no database, account system, or persistent trip storage.

### HOS model

The scheduler stores time in exact minutes. Driving is split whenever the next boundary is reached: eight driving hours, eleven daily driving hours, the fourteen-hour window, seventy cycle hours, or 1,000 route miles. Pickup, delivery, and fuel are on-duty/not-driving periods and satisfy the 30-minute interruption when long enough. A 10-hour sleeper period resets the daily clocks; a 34-hour off-duty event resets the aggregate cycle.

The assessment supplies only total cycle hours used, not the preceding eight daily records. TruckTrack therefore cannot calculate rolling hour recovery and uses a conservative 34-hour restart when the remaining cycle cannot support more driving.

## Repository layout

```text
backend/                 Django project, routing adapter, scheduler, logs, tests
frontend/                React application, map, daily logs, unit and E2E tests
.github/workflows/ci.yml Cross-stack CI checks
LOOM_SCRIPT.md           3–5 minute assessment walkthrough
```

## Local setup

### 1. Routing key

Create a free openrouteservice/HeiGIT API key, then configure the backend:

```bash
cp backend/.env.example backend/.env
```

Set `ORS_API_KEY` in `backend/.env`. The current default API base is `https://api.heigit.org` and can be changed with `ORS_API_BASE_URL`.

### 2. Backend

Python 3.12 and [uv](https://docs.astral.sh/uv/) are recommended.

```bash
cd backend
uv sync --all-groups
set -a; source .env; set +a
uv run python manage.py runserver
```

The API is available at `http://localhost:8000`; OpenAPI UI is at `http://localhost:8000/api/docs/`.

### 3. Frontend

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

Open `http://localhost:5173`.

## API

### `GET /api/v1/health`

Health check for deployments.

### `GET /api/v1/locations?q=Chicago`

Returns normalized location suggestions from the geocoder.

### `POST /api/v1/trips/plan`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "St. Louis, MO",
  "dropoff_location": "Dallas, TX",
  "cycle_hours_used": 18.5,
  "departure_at": "2026-10-03T08:00:00-05:00",
  "terminal_timezone": "America/Chicago",
  "log_metadata": {
    "driver_name": "Alex Morgan",
    "carrier_name": "Northstar Freight"
  }
}
```

The response contains route GeoJSON, route legs and directions, normalized schedule events, map stops, compliance totals, warnings, and per-calendar-day log models.

Errors use one stable shape:

```json
{
  "error": {
    "code": "route_not_found",
    "message": "The requested locations could not be connected by a truck route."
  }
}
```

## Verification

```bash
cd backend
uv run pytest
uv run ruff check .

cd ../frontend
pnpm test
pnpm build
pnpm test:e2e
```

Backend tests use synthetic routes and mocked provider calls, so they do not consume API quota. They cover same-day trips, the eight-hour break, service periods satisfying the break, eleven-/fourteen-hour resets, 1,000-mile fuel stops, a near-exhausted cycle, midnight splits, daily 24-hour totals, and API validation.

## Deployment

Create two Vercel projects from this repository.

### Backend project

- Root directory: `backend`
- Framework preset: Other
- Environment variables:
  - `ORS_API_KEY`
  - `DJANGO_SECRET_KEY`
  - `DJANGO_ALLOWED_HOSTS` (the backend hostname)
  - `CORS_ALLOWED_ORIGINS` (the frontend URL)
- Health check: `/api/v1/health`

The included `backend/vercel.json` sends all requests to the Django WSGI application.

### Frontend project

- Root directory: `frontend`
- Framework preset: Vite
- Environment variable: `VITE_API_BASE_URL` set to the backend origin

The included `frontend/vercel.json` preserves client-side routes.

## External services and attribution

- Routing and geocoding: [openrouteservice](https://openrouteservice.org/), accessed server-side.
- Map rendering: [MapLibre GL JS](https://maplibre.org/) with [OpenFreeMap](https://openfreemap.org/) vector tiles and OpenStreetMap-derived data.
- HOS baseline: [FMCSA property-carrier summary](https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations).

Planned rest and fuel coordinates are points along the route, not verified parking or truck-service facilities. The UI states this explicitly.
