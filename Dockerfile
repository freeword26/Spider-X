FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY spider_x/ ./spider_x/
COPY config/ ./config/

RUN mkdir -p /app/data /app/logs

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8006/health || exit 1

CMD ["uvicorn", "spider_x.core.app:create_app", "--host", "0.0.0.0", "--port", "8006", "--factory"]
