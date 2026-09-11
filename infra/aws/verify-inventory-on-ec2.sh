#!/bin/bash
set -euo pipefail

DATABASE_URL=$(docker inspect yafa-api --format '{{range .Config.Env}}{{println .}}{{end}}' |
  awk -F= '$1=="DATABASE_URL"{sub(/^[^=]*=/,"");print}')

docker run --rm postgres:16-alpine psql "$DATABASE_URL" --tuples-only --no-align --set ON_ERROR_STOP=1 \
  --command "SELECT COUNT(*), MIN(on_hand_quantity), MAX(on_hand_quantity), SUM(on_hand_quantity), COUNT(*) FILTER (WHERE low_stock_threshold=10) FROM inventory_levels;"
