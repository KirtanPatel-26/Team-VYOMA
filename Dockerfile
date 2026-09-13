# Multi-stage lightweight cloud container for Smart Retail Intelligence Hub (₹0 Free Tier)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUN_EDGE_AI=false \
    ENVIRONMENT=cloud \
    PORT=8000

WORKDIR /app

# Install runtime curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight cloud dependencies (under 80MB RAM, zero PyTorch/CUDA)
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy application source code and configurations
COPY app/ ./app/
COPY configs/ ./configs/
COPY data/ ./data/
COPY dashboard/ ./dashboard/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD sh -c "curl -f http://localhost:${PORT:-8000}/api/health || exit 1"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
