# Integration Handoff Specification — Workstreams A & B

**Workstream**: Database Architecture, PostgreSQL & Supabase Integration (Workstream B)  
**Lead Agent**: Google Antigravity  
**Target Integration Branch**: `integration/lannpya-final`  
**Base Commit**: `81a30d7` on `origin/integration/lannpya-final`  
**Feature Branch**: `feature/supabase-postgresql`  
**Live Supabase Cluster**: Verified & Migrated (`PostgreSQL 17.11`, Project Ref: `smcgifjvapdzvpqogtjf`)  

---

## 1. Summary of Published Deliverables

Workstream B has completed all database work under strict isolation from Workstream A:
1. **Driver & Engine**: Configured `psycopg==3.3.6` & SQLAlchemy 2.0 with PostgreSQL 17.11 and SQLite fallback.
2. **Connection Pooling**: Optimized for Supabase Free tier Session Pooler on port `5432` (`pool_size=5`, `max_overflow=5`, `pool_recycle=300`, `pool_pre_ping=True`).
3. **Migrations**: 5 Alembic revisions applied up to head (`0005_routing_plans`).
4. **Verification Suites**:
   - `backend/scripts/verify_database.py` (CLI schema inspector).
   - `backend/scripts/verify_hosted_persistence.py` (Live CRUD, rollback, restart suite).
   - `backend/tests/test_database_compatibility.py` (28/28 passed).
5. **Zero Credentials in Git**: `backend/.env` is strictly git-ignored; zero secrets committed.
6. **Zero Mapping Interference**: Zero modifications to Google Maps, Google Routes, ORS, OR-Tools, or Leaflet files.

---

## 2. Database-to-Mapping Integration Contract (`routing_plans`)

The `routing_plans` table is fully active in PostgreSQL (Supabase) and SQLite. Below is the authoritative contract for Workstream A (ChatGPT + Codex):

### Table Schema (`routing_plans`)
| Column | Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key, `default=uuid4` | Unique plan identifier |
| `actor_id` | `UUID` | `ForeignKey("users.id", ondelete="RESTRICT")`, Index | Dispatcher user ID |
| `version` | `Integer` | `default=1`, `CheckConstraint("version >= 1")` | Optimistic concurrency locking (`version_id_col`) |
| `state` | `String(20)` | `default="PREVIEW"` | Lifecycle state: `"PREVIEW"` or `"COMMITTED"` |
| `created_at` | `DateTime(timezone=True)` | `default=utcnow` | Plan generation timestamp in UTC |
| `data` | `JSON` / `JSONB` | Non-null | Complete optimization payload |

---

### Payload Structure (`data` JSON / JSONB)

The JSON payload stored in `routing_plans.data` must adhere to the following structure:

```json
{
  "query": {
    "origin": {
      "latitude": 16.8052145,
      "longitude": 96.1558231
    },
    "orders": [
      {
        "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "demand": 1,
        "service_seconds": 180,
        "priority": 0
      }
    ],
    "riders": [
      {
        "rider_id": "8fa85f64-5717-4562-b3fc-2c963f66afa7",
        "capacity": 20
      }
    ],
    "operating_window": {
      "start": "2026-10-22T08:00:00Z",
      "end": "2026-10-22T18:00:00Z"
    },
    "return_to_hub": true,
    "mode": "DRIVE",
    "allow_simulation": false,
    "objective": "duration",
    "solver_seconds": 2
  },
  "basis": {
    "orders": {
      "3fa85f64-5717-4562-b3fc-2c963f66afa6": {
        "version": 1,
        "latitude": 16.8052145,
        "longitude": 96.1558231,
        "delivery_time_window": "10:00 - 14:00"
      }
    },
    "riders": {
      "8fa85f64-5717-4562-b3fc-2c963f66afa7": {
        "version": 1,
        "queue_version": 0,
        "operational_status": "AVAILABLE"
      }
    }
  },
  "result": {
    "solver": "OR-Tools",
    "solver_status": "FEASIBLE",
    "globally_optimal": false,
    "elapsed_ms": 142.5,
    "provider": "google",
    "quality": "ROAD_STATIC",
    "traffic_aware": false,
    "matrix_size": 4,
    "vehicles": [
      {
        "rider_id": "8fa85f64-5717-4562-b3fc-2c963f66afa7",
        "distance_meters": 4200,
        "duration_seconds": 900,
        "travel_seconds": 720,
        "capacity": 20,
        "load": 1,
        "geometry": {
          "type": "LineString",
          "coordinates": [
            [96.1558231, 16.8052145],
            [96.1561000, 16.8062000]
          ]
        },
        "geometry_warning": null,
        "stops": [
          {
            "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "sequence": 1,
            "arrival": "2026-10-22T08:15:00Z",
            "departure": "2026-10-22T08:18:00Z",
            "demand": 1,
            "latitude": 16.8052145,
            "longitude": 96.1558231,
            "priority": 0,
            "delivery_window": null
          }
        ]
      }
    ],
    "unassigned": [],
    "warnings": [],
    "attribution": "Google Maps Routes API"
  },
  "routes": {
    "8fa85f64-5717-4562-b3fc-2c963f66afa7": "cfa85f64-5717-4562-b3fc-2c963f66afa8"
  }
}
```

---

### Field Specifications & Invariants

1. **Coordinates**:
   - `latitude`: `float` within `[-90.0, 90.0]`.
   - `longitude`: `float` within `[-180.0, 180.0]`.
   - GeoJSON `geometry.coordinates`: Formatted as `[longitude, latitude]` pairs (GeoJSON standard RFC 7946).
2. **Distance Units**:
   - `distance_meters`: Non-negative `integer` in **meters**. (Example: `4200` = 4.2 km).
3. **Time & ETA Units**:
   - `duration_seconds`: Total vehicle itinerary duration in **seconds** (`integer >= 0`).
   - `travel_seconds`: In-transit driving time in **seconds** (`integer >= 0`).
   - `service_seconds`: On-site dwell time in **seconds** (`integer >= 0`).
   - Timestamps (`arrival`, `departure`, `start`, `end`, `created_at`): ISO 8601 strings in **UTC** with explicit timezone indicator (`Z` or `+00:00`).
4. **Solver & Quality Values**:
   - `solver`: Literal `"OR-Tools"`.
   - `solver_status`: `"FEASIBLE"`, `"PARTIAL"`, `"INFEASIBLE"`, or `"TIME_LIMIT"`.
   - `quality`: `"SIMULATED"` (fallback Euclidean) or `"ROAD_STATIC"` (real road network matrix).
5. **Stop Sequence**:
   - `sequence`: 1-indexed strictly positive integer (`1, 2, 3...`).
6. **Optimistic Versioning & Concurrency**:
   - `RoutingPlan` uses `version_id_col` starting at `1`.
   - To commit a plan via `POST /api/routing/plans/{id}/commit`, the client must submit `expected_version`. If another dispatcher updated or committed the plan, `409 VERSION_CONFLICT` is returned.
   - If orders or riders within `plan.data["basis"]` changed status or version between preview and commit, `409 ROUTE_PLAN_STALE` is returned.

---

## 3. Potential Conflict Analysis with Mapping Branch

| Area | Conflict Risk | Mitigation / Verification |
| :--- | :--- | :--- |
| **Google Routes & ORS Adapters** | **NONE (0%)** | Workstream B never opened or modified adapter files. |
| **OR-Tools Solver Logic** | **NONE (0%)** | Optimization algorithms in `backend/app/routing/` were untouched. |
| **API Endpoints (`app/api/routing.py`)** | **NONE (0%)** | Endpoint contracts were fully preserved. |
| **Alembic Migration History** | **NONE (0%)** | Workstream B built on `0005_routing_plans` without altering previous migration hashes. |
| **Requirements / Dependencies** | **NONE (0%)** | Added `psycopg==3.3.6` to `requirements-dev.lock`. Compatible with all existing packages on Python 3.13. |
| **Configuration Aliasing** | **NONE (0%)** | Recognizes both `LANNPYA_DATABASE_URL` and `DATABASE_URL`. |

---

## 4. Integration Readiness

Both branches branch from `81a30d7` on `origin/integration/lannpya-final`.

When combining into `integration/lannpya-final`:
```bash
git checkout integration/lannpya-final
git pull origin integration/lannpya-final
git merge feature/supabase-postgresql
# Run automated verification suite
pytest backend/tests/test_database_compatibility.py
python backend/scripts/verify_database.py
```
Since file sets are strictly disjoint, the merge will be clean and fast-forward or clean recursive merge with zero code conflicts.
