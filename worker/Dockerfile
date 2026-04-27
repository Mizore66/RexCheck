# ==============================================================================
# rexcheck Python Ingestion Worker Dockerfile
# Optimized for AWS ECS Fargate deployment
# ==============================================================================

FROM python:3.12-slim AS runtime

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system --gid 1000 worker && \
    useradd --system --uid 1000 --gid worker --create-home worker

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY . .

# Set ownership
RUN chown -R worker:worker /app

USER worker

# Runtime configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import redis; r = redis.from_url('${REDIS_URL:-redis://localhost:6379/0}'); r.ping()" || exit 1

CMD ["python", "ingestion_worker.py"]
