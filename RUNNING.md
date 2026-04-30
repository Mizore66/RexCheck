# How to Run Rexcheck

This guide covers the recommended **Docker Compose** workflow and an optional **native** (Rails on your machine) workflow. DexGuard uses Rails 8, PostgreSQL 16, Redis 7, Solid Queue for jobs, an optional Python ingestion worker, and the **xgb** gem for ML health scores (`lib/ml_models/`).

---

## Prerequisites

### Docker path (recommended)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- Enough disk for images (~2–3 GB) and RAM (~4 GB+ for Postgres + Rails)
- **Important:** Docker Desktop must be running (daemon healthy). On Windows you may see errors like `cannot connect to Docker API` until the VM/Linux backend is fully started.

### Native path (optional)

- Ruby **3.3.x** (see `Gemfile` / `Gemfile.lock`)
- PostgreSQL **16+**
- Redis **7+**
- Node.js **18+** and npm (for `esbuild` + Tailwind CLI)
- Bundler (`gem install bundler`)

---

## Configuration

1. Copy the example environment file and adjust secrets for non-local deployments:

```bash
cp .env.example .env
```

Local defaults expect:

| Variable | Typical local value |
|----------|---------------------|
| `DATABASE_HOST` | `localhost` (native) or `db` (inside Compose) |
| `DATABASE_USERNAME` / `PASSWORD` | `postgres` / `postgres` (matches Compose) |
| `REDIS_URL` | `redis://localhost:6379/0` (native) or `redis://redis:6379/0` (Compose) |

Optional ML-related toggle (see `.env.example`):

- **`DEXGUARD_USE_HEURISTIC_SCORE`** — Set to `true` only if you need the legacy heuristic score instead of `lib/ml_models/xgboost_model.json`.

Compose already injects Redis/Postgres URLs for services that use `docker-compose.yml`; your `.env` is mainly used when you run Rails **outside** the container against local services.

---

## Option A — Docker Compose (recommended)

From the repository root.

### 1. Start Docker Desktop / engine

Ensure `docker ps` works with no connection errors.

### 2. Build images (first time or after Dockerfile / Gemfile changes)

```bash
docker compose build
```

### 3. Start dependencies first (optional but faster debugging)

```bash
docker compose up -d db redis
```

Wait until Postgres is healthy (~10–30 seconds).

### 4. Prepare the database

```bash
docker compose run --rm web bundle exec rails db:prepare
```

This creates the DB if needed and runs migrations. Repeat once if Postgres was not ready (`connection refused`).

Optional demo data:

```bash
docker compose run --rm web bundle exec rails db:seed
```

### 5. Start the full stack

```bash
docker compose up -d --build
```

Services include:

| Service | Role |
|---------|------|
| `web` | Rails + Puma on port **3000** (runs bundle install / npm builds on startup per `docker-compose.yml`) |
| `worker` | Solid Queue worker |
| `db` | PostgreSQL |
| `redis` | Redis for queues/cache |
| `ingestion` | Python GeckoTerminal polling worker |

### 6. Verify

Open the dashboard:

http://localhost:3000  

Sample MCP API:

```bash
curl -s "http://localhost:3000/api/v1/mcp/pool_status?address=0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640&network=eth"
```

### Useful Docker commands

```bash
# Follow logs
docker compose logs -f web

# Stop everything
docker compose down

# Rebuild after Gemfile/package changes
docker compose up --build -d
```

---

## Option B — Native Rails (no Docker)

Use this only if Docker is unavailable.

### 1. Install services

Install and start PostgreSQL and Redis locally, and create databases `rexcheck_development` / `rexcheck_test` matching `config/database.yml`, or rely on defaults with user `postgres`.

### 2. Install deps and compile assets

```bash
bundle install
npm install
npm run build
npm run build:css
```

Alternatively:

```bash
bin/setup
```

(`bin/setup` runs `bundle install`, `npm install`, `db:prepare`, and asset builds.)

### 3. Start Redis and Postgres

Ensure they listen where `.env` points (default `localhost`).

### 4. Run the app

Terminal 1 — web:

```bash
bundle exec rails s
```

Terminal 2 — Solid Queue (required for background jobs such as Redis pool ingestion):

```bash
bundle exec rails solid_queue:start
```

(Optionally skip the worker if you only need static UI; ingestion from Redis will not process.)

### 5. Open the browser

http://localhost:3000  

---

## Optional — ML training artifacts (DexGuard model)

Scores use `lib/ml_models/xgboost_model.json` when the **`xgb`** gem loads successfully. To regenerate artifacts from the Python pipeline:

```bash
py -3.12 -m venv .venv-ml
.\.venv-ml\Scripts\python -m pip install -r scripts/requirements.txt
.\.venv-ml\Scripts\python scripts/fetch_historical_data.py --mode synthetic --rows 10000
.\.venv-ml\Scripts\python scripts/train_model.py --trials 30
```

Output is written to `lib/ml_models/xgboost_model.json` and `feature_schema.json`. See `scripts/README.md` for details.

---

## MCP server + Cursor client setup

Rexcheck includes a local stdio MCP server at `mcp_server/index.js` that exposes:

- `ping`
- `list_tokens`
- `analyze_token`
- `get_pool_status`

### 1. Install MCP server dependencies

```bash
cd mcp_server
npm install
```

### 2. Ensure Rails is running

The MCP tools call the Rails API (default `http://localhost:3000`), so keep Docker/native Rails up.

### 3. Cursor MCP client registration

Project-scoped config is pre-created at:

`./.cursor/mcp.json`

It points to:

- command: `node`
- args: `mcp_server/index.js`
- env: `RAILS_API_URL=http://localhost:3000`

After editing/saving `mcp.json`, restart Cursor.

### 4. Verify in Cursor

1. Open a new chat in this workspace and check tools are listed.
2. Call `ping` first (connectivity smoke test).
3. Call `list_tokens` to confirm live Rails data.
4. Call `get_pool_status` with:
   - address: `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`
   - network: `eth`

If tools do not appear, open Cursor MCP logs (`Output` -> `MCP Logs`) and check JSON syntax / command path.

---

## Troubleshooting

| Symptom | What to try |
|---------|--------------|
| `failed to connect to the docker API` / `DockerDesktopLinuxEngine` | Start **Docker Desktop** and wait until it reports “running”; retry `docker ps`. |
| `connection refused` to Postgres during `db:prepare` | Wait for the `db` healthcheck (`docker compose ps`) or rerun `rails db:prepare`. |
| Port **3000** in use | Stop the other process or change the host port in `docker-compose.yml`. |
| `bundle` / `rails` not found (native path) | Use Ruby **3.3.x** via rbenv/asdf/DevKit; reopen the shell after install. |
| ML gem fails to load | Install OS deps implied by **`xgb`** (see [ankane/xgb](https://github.com/ankane/xgb)); or set **`DEXGUARD_USE_HEURISTIC_SCORE=true`** to use heuristic scoring only. |
| `esbuild` missing (native path) | Run `npm install` from the repo root. |

---

## Related files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service topology and env injection |
| `Dockerfile` | Rails container build |
| `worker/Dockerfile` | Python ingestion worker |
| `.env.example` | Environment variables template |
| `scripts/README.md` | ML fetch/train scripts |

For a shorter Docker-only cheatsheet you can still skim `LOCAL_SETUP.md` (it redirects here).
