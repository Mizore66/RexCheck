# Running RexCheck Locally

The full runbook (Docker Compose, native Rails, ML pipeline, troubleshooting) lives in **[RUNNING.md](RUNNING.md)**.

Docker quick reminder:

```bash
docker compose build
docker compose up -d
docker compose run --rm web bundle exec rails db:prepare
```

Open [http://localhost:3000](http://localhost:3000).
