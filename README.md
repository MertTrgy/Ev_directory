# OpenEV Ingestion Service + React UI

This repository now has two parts:

- A FastAPI ingestion service that syncs OpenEV data into PostgreSQL.
- A React + TypeScript UI that shows vehicles as cards and opens a drawer with full details.

## Architecture

- `db` (PostgreSQL): stores raw vehicle payloads (`jsonb`).
- `liquibase`: creates/updates schema using changelog files.
- `api` (FastAPI): syncs and serves vehicle data to UI.
- `frontend` (React + TypeScript + Vite): cards + "More info" drawer.

## Database Migrations (Liquibase)

Schema creation is migration-driven now (no SQLAlchemy `create_all` at startup).

- Master changelog: `liquibase/changelog/db.changelog-master.xml`
- Initial schema: `liquibase/changelog/changes/001_init.xml`

The migration creates:

- `evdb_vehicle_raw`
- Unique constraint on `(source_name, source_vehicle_id, market)`
- Indexes on `vehicle_slug`, `vehicle_name`, `market`

## Backend (FastAPI)

Main backend files:

- `app/main.py`: API endpoints + CORS
- `app/service.py`: sync logic and read/query helpers
- `app/provider.py`: OpenEV API pagination + detail fetch
- `app/models.py`: SQLAlchemy model used by the app
- `app/config.py`: environment settings

### Backend endpoints

- `GET /health`
- `POST /sync`
- `POST /sync/update`
- `GET /vehicles?limit=24&offset=0`
- `GET /vehicles/{vehicle_id}`

## Frontend (React + TypeScript)

Frontend lives in `frontend/`.

- `frontend/src/App.tsx`: page composition and state management
- `frontend/src/api.ts`: typed API client
- `frontend/src/types.ts`: TypeScript DTOs
- `frontend/src/components/VehicleCard.tsx`: card UI
- `frontend/src/components/VehicleDrawer.tsx`: right-side drawer UI
- `frontend/src/index.css`: visual system, responsive layout, animations

### UI behavior

- Cards show key info (name, source ID, market, updated time).
- Card image uses API image when available, otherwise `frontend/public/car-placeholder.svg`.
- `More info` opens a drawer and loads full vehicle payload.
- Drawer shows summary metadata + full JSON payload.

## Environment Variables

Use `.env.example` as base.

Required:

- `DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/evdb`
- `EVDB_DATA_URL=http://host.docker.internal:3000/api/v1/vehicles/list`

Common optional:

- `EVDB_VEHICLE_DETAIL_URL_TEMPLATE=http://host.docker.internal:3000/api/v1/vehicles/code/{unique_code}`
- `EVDB_PAGE_SIZE=100`
- `EVDB_FETCH_VEHICLE_DETAILS=true`
- `CORS_ORIGINS=http://localhost:5173`
- `LOG_LEVEL=INFO`

Frontend:

- `frontend/.env.example` contains `VITE_API_BASE_URL=http://localhost:8000`

## Run with Docker Compose

```bash
docker compose up --build
```

Services and ports:

- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- Postgres: `localhost:5432`

## Learning Notes (React + TypeScript)

If you want to learn implementation details, start here:

1. `frontend/src/types.ts`  
   This is your contract layer. Keep API response types here first.
2. `frontend/src/api.ts`  
   Wrap `fetch` in a typed helper (`requestJson<T>`) so each endpoint returns known shapes.
3. `frontend/src/App.tsx`  
   Keep UI state in one place: list state, drawer state, loading/error states.
4. `frontend/src/components/VehicleCard.tsx` and `VehicleDrawer.tsx`  
   Move presentational UI into components so App stays readable.

I also added short comments in the React code in places that matter most:

- Detail caching strategy in `App.tsx`
- Escape-key handling in `VehicleDrawer.tsx`
- Shared request helper in `api.ts`

## Notes

- `https://open-ev-data.github.io/latest/api/` is documentation, not a hosted data API.
- Point `EVDB_DATA_URL` to a reachable OpenEV API instance.
