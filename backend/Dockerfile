# Single-worker by default, matching README "Deployment" — utils/cache.py and utils/limiter.py
# are process-local in-memory stores with no Redis backend, so WEB_CONCURRENCY must stay 1
# unless that's swapped out first.
FROM python:3.12-slim

WORKDIR /app

# No compiled extensions in requirements.txt need system build tools beyond what manylinux
# wheels already cover (cryptography, Pillow all ship prebuilt wheels for this base image).
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
