# Running RexCheck Locally

Welcome to RexCheck! If you've just cloned or forked this repository, follow the steps below to get your local environment running smoothly using Docker.

## Prerequisites
- Docker & Docker Compose
- Ensure Docker Desktop is running before proceeding.

## Step-by-Step Setup

### 1. Build the Docker Containers
Our setup includes a Rails application, a Python ingestion worker, Redis, and PostgreSQL. To build the images locally:
```bash
docker-compose build
```
*Note: Due to a `.dockerignore` file, `node_modules` is automatically excluded to prevent context limits, ensuring a fast build.*

### 2. Start the Services
Run all services in the background:
```bash
docker-compose up -d
```

### 3. Initialize the Database
The PostgreSQL database needs to be created, migrated, and optionally seeded before you can view data. Execute:
```bash
docker-compose run web bundle exec rails db:prepare
```
*(If rails gives connection errors, wait a few seconds and run the command again as Postgres might still be accepting connections)*

### 4. Application Verification
Once the database is ready, you can start testing:
- **Web Dashboard:** Visit [http://localhost:3000](http://localhost:3000)
- **API Endpoint:** Test the pool status via the MCP endpoint:
```bash
curl -s "http://localhost:3000/api/v1/mcp/pool_status?address=0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640&network=eth"
```

## Useful Commands
- Tail logs for all services: `docker-compose logs -f`
- Stop the environment: `docker-compose down`
- Rebuild after a Gemfile or package.json change: `docker-compose up --build -d`
