#!/bin/sh
# Waits for MySQL to accept TCP connections (docker-compose's mysql service can take a few
# seconds to finish initializing even after the container starts), then applies migrations and
# hands off to gunicorn. A plain TCP probe is enough here — alembic upgrade head is idempotent
# and will surface its own real connection errors if MySQL is actually misconfigured.
set -e

python - <<'PY'
import os
import socket
import sys
import time

host = os.environ.get("MYSQL_HOST", "localhost")
port = int(os.environ.get("MYSQL_PORT", "3306"))

for attempt in range(30):
    try:
        with socket.create_connection((host, port), timeout=3):
            sys.exit(0)
    except OSError:
        print(f"Waiting for MySQL at {host}:{port}... ({attempt + 1}/30)")
        time.sleep(2)

print(f"MySQL at {host}:{port} never became reachable")
sys.exit(1)
PY

alembic upgrade head

# --graceful-timeout 30: on SIGTERM (docker stop / a rolling deploy), gunicorn stops accepting
# new connections immediately but gives each worker up to 30s to finish requests already in
# flight before force-killing it — main.py's lifespan shutdown (engine.dispose(), stopping the
# cache/revocation sweepers) only runs after that drain completes, not before.
exec gunicorn -w "${WEB_CONCURRENCY:-1}" -k uvicorn.workers.UvicornWorker --graceful-timeout 30 -b 0.0.0.0:8000 main:app
