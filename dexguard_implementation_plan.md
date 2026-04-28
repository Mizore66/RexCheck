# SYSTEM DIRECTIVE: DEXGUARD IMPLEMENTATION PLAN
**Target Agent:** Claude Opus 4.7 (or equivalent High-Capability Coding Agent)
**Role:** Senior Full-Stack Architect & DevSecOps Engineer.
**Execution Parameters:** NO ASSUMPTIONS ALLOWED. You must follow this specification exactly as written. Do not deviate from the tech stack, styling, architecture, or naming conventions. If a design decision seems missing, refer back to the rules in this document—do not invent your own.

---

## 1. SYSTEM ARCHITECTURE & TECH STACK
You will build a two-part hybrid system. Do not use React, Next.js, or any Single Page Application (SPA) frameworks for the frontend. 

**Component A: The Ingestion Worker (Python)**
* **Language:** Python 3.12+
* **Libraries:** `aiohttp` (for async GeckoTerminal API requests), `redis` (for caching), `pybloom_live` (for Bloom filtering).
* **Purpose:** Continuously poll/stream new pool data from GeckoTerminal, apply a Bloom filter to reject duplicates, and push raw JSON payloads of new pools into a Redis queue (`dexguard:raw_pools`).

**Component B: The Intelligence & API Layer (Ruby on Rails)**
* **Framework:** Ruby on Rails 8.0+
* **Database:** PostgreSQL 16+ (Primary Cold/Warm storage).
* **Queue System:** `Solid Queue` (Native Rails 8 background processing).
* **Cache/State:** Redis (Hot tier storage & communication with Python worker).
* **Frontend:** Rails Hotwire (Turbo + Stimulus) with TailwindCSS.
* **Purpose:** Consume from Redis, calculate the "Health Score", persist historical data to Postgres, serve the HTML dashboard, and expose the Model Context Protocol (MCP) JSON API for AI Agents.

---

## 2. DATABASE SCHEMA (POSTGRESQL)
Implement the following exact schema in Rails ActiveRecord.

**Table: `pools`**
* `id`: UUID, Primary Key
* `network_id`: String (e.g., 'eth', 'solana', 'base'), Index
* `pool_address`: String, Unique Index
* `base_token_address`: String
* `quote_token_address`: String
* `created_at`, `updated_at`: Datetime

**Table: `pool_scans`**
* `id`: UUID, Primary Key
* `pool_id`: UUID (Foreign Key to `pools`), Index
* `volume_usd`: Decimal (precision: 18, scale: 2)
* `reserve_in_usd`: Decimal (precision: 18, scale: 2)
* `health_score`: Integer (0 to 100)
* `flags`: JSONB (Array of string warnings, e.g., `["low_liquidity", "high_velocity"]`)
* `scanned_at`: Datetime, Index

---

## 3. HEURISTIC ENGINE (THE "HEALTH SCORE")
Do not invent your own algorithm. Implement this exact logic in a Rails Service Object (`App::Services::RiskCalculator`):

1.  **Base Score:** Start at 100.
2.  **Liquidity Depth Check:** If `reserve_in_usd` < $10,000, subtract 50 points. Flag: `"critical_low_liquidity"`.
3.  **Volume/Liquidity Ratio Check:** If `volume_usd` > (`reserve_in_usd` * 10), subtract 30 points. Flag: `"wash_trading_suspected"`.
4.  **Age Check:** (Calculated from GeckoTerminal metadata). If pool age < 1 hour, subtract 10 points. Flag: `"unseasoned_pool"`.
5.  **Status Assignment:**
    * Score 80-100: `status: "SAFE"`
    * Score 50-79: `status: "WARNING"`
    * Score < 50: `status: "DANGER"`

---

## 4. API SPECIFICATION (FOR EXTERNAL AI AGENTS)
Expose exactly this endpoint. Do not add authentication for this MVP phase.

* **Endpoint:** `GET /api/v1/mcp/pool_status`
* **Parameters:** `address` (string, required), `network` (string, required)
* **Response Format (Strict JSON):**
    ```json
    {
      "pool_address": "0x...",
      "status": "DANGER",
      "health_score": 45,
      "recommendation": "DO_NOT_TRADE",
      "flags": ["critical_low_liquidity"]
    }
    ```

---

## 5. UI/UX STYLING & DESIGN LANGUAGE
Do not use Bootstrap. Do not use generic Tailwind defaults without this specific color mapping. The UI must reflect a "Fintech / Cyber-Security Sentinel" theme.

* **Typography:** Use `'Inter'` for all standard text. You MUST use `'JetBrains Mono'` for all contract addresses, numerical values, and code snippets.
* **Color Palette (Dark Mode ONLY):**
    * Background (Body): `bg-slate-950`
    * Cards / Panels: `bg-slate-900 border border-slate-800`
    * Primary Text: `text-slate-200`
    * Secondary Text: `text-slate-400`
    * Safe / Positive Action: `text-emerald-400`, Backgrounds: `bg-emerald-900/30 border-emerald-800`
    * Warning: `text-amber-400`, Backgrounds: `bg-amber-900/30 border-amber-800`
    * Danger / Alert: `text-rose-500`, Backgrounds: `bg-rose-900/30 border-rose-800`
* **Layout:** Single-page dashboard driven by Turbo Frames. A fixed left sidebar (`w-64`) for navigation, and a main content area for the "Real-Time Pool Grid". The grid must use CSS Grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`).

---

## 6. INFRASTRUCTURE & DEPLOYMENT PROTOCOL
Do not write configuration for Heroku or Vercel. 

The application must be fully containerized. Generate the necessary Dockerfiles optimized for deployment on AWS ECS Fargate. The Rails application and the Python asyncio worker must be definable as separate Fargate tasks within the same cluster. 

Additionally, configure the Rails active storage and log archiving to target an AWS S3 bucket. This ensures that historical "cold tier" pool data and large system logs are offloaded from the primary PostgreSQL database, maintaining query performance.

---

## 7. EXECUTION STEPS
1.  Initialize the Rails 8 project with PostgreSQL and esbuild/Tailwind.
2.  Generate the Python worker script in a `worker/` directory at the project root.
3.  Write the ActiveRecord models and migrations.
4.  Implement the `RiskCalculator` service.
5.  Build the Hotwire dashboard using the exact Tailwind classes specified.
6.  Generate the `Dockerfile` for Rails, the `Dockerfile` for the Python worker, and a `docker-compose.yml` for local testing.
