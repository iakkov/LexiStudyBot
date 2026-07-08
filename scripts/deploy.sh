#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ! -f .env ]]; then
  echo "Deployment stopped: .env is missing on the VPS."
  exit 1
fi

docker compose config >/dev/null
docker compose build --pull bot
docker compose up -d --remove-orphans

for attempt in {1..30}; do
  postgres_id="$(docker compose ps -q postgres)"
  bot_id="$(docker compose ps -q bot)"

  postgres_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$postgres_id" 2>/dev/null || true)"
  bot_status="$(docker inspect --format '{{.State.Status}}' "$bot_id" 2>/dev/null || true)"

  if [[ "$postgres_health" == "healthy" && "$bot_status" == "running" ]]; then
    echo "Deployment completed: PostgreSQL is healthy and the bot is running."
    docker compose ps
    exit 0
  fi

  sleep 2
done

echo "Deployment failed health verification."
docker compose ps -a
docker compose logs --no-color --tail=100 postgres bot
exit 1
