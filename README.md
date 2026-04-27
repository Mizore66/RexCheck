# rexcheck — Pool Intelligence Sentinel

> Real-time DeFi pool health scoring and risk analysis powered by GeckoTerminal data.

![rexcheck](https://img.shields.io/badge/rexcheck-v1.0.0--sentinel-emerald) ![Rails](https://img.shields.io/badge/Rails-8.0-red) ![Python](https://img.shields.io/badge/Python-3.12-blue) ![Docker](https://img.shields.io/badge/Docker-Compose-blue)

---

## Architecture

rexcheck is a **two-part hybrid system**:

| Component | Tech | Purpose |
|-----------|------|---------|
| **Ingestion Worker** | Python 3.12 + asyncio | Polls GeckoTerminal API, Bloom-filters duplicates, pushes to Redis |
| **Intelligence Layer** | Rails 8 + Hotwire | Consumes from Redis, calculates Health Score, serves dashboard & MCP API |

```
┌──────────────────┐     ┌─────────┐     ┌──────────────────┐     ┌──────────┐
│  GeckoTerminal   │────▶│  Python │────▶│     Redis        │────▶│  Rails 8 │
│  API (v2)        │     │  Worker │     │  rexcheck:       │     │  Solid   │
│                  │     │  async  │     │  raw_pools       │     │  Queue   │
└──────────────────┘     └─────────┘     └──────────────────┘     └────┬─────┘
                                                                       │
                                              ┌────────────────────────┤
                                              ▼                        ▼
                                         ┌──────────┐          ┌──────────────┐
                                         │ PostgreSQL│          │   Hotwire    │
                                         │ 16       │          │   Dashboard  │
                                         └──────────┘          └──────────────┘
```

## Quick Start (Docker)

```bash
# Clone and start everything
cd rexcheck
docker-compose up --build

# In another terminal, setup the database
docker-compose run web bundle exec rails db:create db:migrate db:seed

# Visit the dashboard
open http://localhost:3000
```

## API Endpoint

### `GET /api/v1/mcp/pool_status`

Query parameters:
- `address` (string, required) — Pool contract address
- `network` (string, required) — Network identifier (e.g., `eth`, `solana`, `base`)

**Example:**
```bash
curl "http://localhost:3000/api/v1/mcp/pool_status?address=0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640&network=eth"
```

**Response:**
```json
{
  "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
  "status": "SAFE",
  "health_score": 100,
  "recommendation": "TRADE_WITH_CAUTION",
  "flags": []
}
```

## Health Score Algorithm

| Check | Condition | Penalty | Flag |
|-------|-----------|---------|------|
| Liquidity Depth | `reserve_in_usd < $10,000` | -50 | `critical_low_liquidity` |
| Wash Trading | `volume > reserve × 10` | -30 | `wash_trading_suspected` |
| Pool Age | `age < 1 hour` | -10 | `unseasoned_pool` |

**Status Assignment:**
- `80-100` → **SAFE** → `TRADE_WITH_CAUTION`
- `50-79` → **WARNING** → `MONITOR_CLOSELY`
- `< 50` → **DANGER** → `DO_NOT_TRADE`

## Deployment (AWS ECS Fargate)

The project includes optimized Dockerfiles for Fargate deployment:

1. **Rails Task:** `Dockerfile` (multi-stage, ~120MB)
2. **Python Worker Task:** `worker/Dockerfile` (~80MB)

Both are designed to run as separate Fargate tasks within the same ECS cluster, sharing a Redis ElastiCache instance and RDS PostgreSQL database.

## Environment Variables

See `.env.example` for the complete list of required environment variables.

## License

MIT
