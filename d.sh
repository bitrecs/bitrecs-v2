#!/usr/bin/env bash

set -euo pipefail

# ────────────────────────────────────────────────
#  CONFIGURATION
# ────────────────────────────────────────────────

COMPOSE_FILE="./validator/docker-compose-prod.yml"
SERVICE="validator"

# How long to wait before trying to fetch logs (give container time to start)
SLEEP_BEFORE_LOGS=3

# ────────────────────────────────────────────────

echo "→ Stopping $SERVICE..."
docker compose -f "$COMPOSE_FILE" stop "$SERVICE" 2>/dev/null || true

echo "→ Building..."
docker compose -f "$COMPOSE_FILE" build --pull "$SERVICE"

echo "→ Starting..."
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"

echo "→ Logs (Ctrl+C to exit)"

sleep "$SLEEP_BEFORE_LOGS"

# ─── Get the actual container name / ID from compose ────────────────────────

# --quiet     → only output container IDs
# --all       → include stopped ones (but we just started it, so should be running)
# We take the first line in case of multiple replicas (scale > 1)
CONTAINER=$(docker compose -f "$COMPOSE_FILE" ps --quiet --all "$SERVICE" | head -n 1)

if [ -z "$CONTAINER" ]; then
    echo "Error: Could not find any container for service '$SERVICE'"
    echo "→ Try: docker compose -f '$COMPOSE_FILE' ps"
    exit 1
fi

# Optional: show what we're attaching to (helps debugging)
echo "Following logs of container: $CONTAINER"
echo "(use Ctrl+C to stop following)"

# ─── Attach to logs ─────────────────────────────────────────────────────────

docker logs -f --tail 10 "$CONTAINER"