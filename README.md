# Road Networks FastAPI — Quick Start

Small **FastAPI + Postgres/PostGIS** service that:

- lets a customer **upload a road network** (GeoJSON _LineStrings_)
- **versions** it on every update (no deletes; old version is closed with `valid_to`)
- serves **edges as GeoJSON**, including **time-travel** via `?datetime=...`
- Auth is by **`X-API-Key`** header

---

## Run it

**1) Build & start**
```bash
docker compose up --build -d
```

**2) Migrate database**
```bash
docker compose exec api alembic upgrade head
```

**3) Seed one demo customer + API key (`dev-123`)**
```bash
docker compose exec api python /app/ingest_bundle/seed_minimal.py
```

Open docs: **http://localhost:8000/docs**

---

## API (the three tasks)

> All requests need: `-H 'X-API-Key: dev-123'`

### Task 1 — Create a network (first upload)

**POST** `/networks`

```bash
curl -s -H 'X-API-Key: dev-123'   -F name='Network 1'   -F file=@ingest_bundle/file-1.geojson   http://localhost:8000/networks | jq .
```

---

### Task 2 — Update a network (new version)

**POST** `/networks/update`

```bash
curl -s -H 'X-API-Key: dev-123'   -F name='Network 1'   -F file=@ingest_bundle/file-2.geojson   http://localhost:8000/networks/update | jq .
```

Creates a new row in `network_versions` and stores the new edges under it.  
Older edges remain, but are no longer “current”.

---

### Task 3 — Get edges as GeoJSON (with time-travel)

**GET** `/networks/{network_id}/edges?datetime=2025-09-06T05:10:00Z`

- `datetime` is **optional**. If omitted, “now” (UTC) is used.
- Timestamp format: **RFC3339 / ISO-8601** (e.g. `...Z`)

**Examples**

**Current snapshot**
```bash
curl -s -H 'X-API-Key: dev-123'   "http://localhost:8000/networks/<NETWORK_ID>/edges"   | jq '.features | length'
```

**State BEFORE an update** (pick a time between `valid_from..valid_to` of the old version)
```bash
curl -s -H 'X-API-Key: dev-123'   "http://localhost:8000/networks/<NETWORK_ID>/edges?datetime=$TS"   | jq '.features | length'
```

**State AFTER the update** (`>=` new `valid_from`)
```bash
curl -s -H 'X-API-Key: dev-123'   "http://localhost:8000/networks/<NETWORK_ID>/edges?datetime=$TS"   | jq '.features | length'
```
