#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BASE="${BASE:-http://127.0.0.1:8000}"

nohup "$ROOT/.venv/bin/uvicorn" app.main:app --port 8000 >/tmp/gate_uvicorn.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 2

PY="$ROOT/.venv/bin/python"
EMAIL="gate$(date +%s)@example.com"

echo "== health =="
curl -s "$BASE/health"
echo

echo "== register + login =="
curl -s -o /dev/null -X POST "$BASE/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"supersecret1\"}"
TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"supersecret1\"}" \
  | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "== create widget =="
WIDGET=$(curl -s -X POST "$BASE/api/v1/widgets" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"signup_form","title":"Gate Widget","fields":[{"name":"email","label":"Email","type":"email","required":true}],"allowed_origins":["http://localhost:5500"]}')
WID=$(printf '%s' "$WIDGET" | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["id"])')
SNIPPET=$(printf '%s' "$WIDGET" | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["embed_snippet"])')
echo "widget: $WID"
echo "snippet: $SNIPPET"

KEY1=$("$PY" -c 'import uuid; print(uuid.uuid4())')

echo "== cross-origin submission (expect 201) =="
curl -s -i -X POST "$BASE/api/v1/public/submissions" \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
  -d "{\"widget_id\":\"$WID\",\"fields\":{\"email\":\"lead@example.com\"},\"idempotency_key\":\"$KEY1\"}" \
  | sed -n '1p;/^{/p'

echo "== replay same key (expect 200 + X-Idempotent-Replay) =="
curl -s -i -X POST "$BASE/api/v1/public/submissions" \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
  -d "{\"widget_id\":\"$WID\",\"fields\":{\"email\":\"lead@example.com\"},\"idempotency_key\":\"$KEY1\"}" \
  | grep -iE '^(HTTP|x-idempotent-replay)' || true

echo "== disallowed origin (expect 403) =="
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/public/submissions" \
  -H 'Content-Type: application/json' -H 'Origin: http://evil.example.net' \
  -d "{\"widget_id\":\"$WID\",\"fields\":{\"email\":\"e@x.com\"}}"

echo "== malformed payload (expect 400) =="
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/public/submissions" \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
  -d "{\"widget_id\":\"$WID\",\"fields\":{\"wrong\":\"shape\"}}"

echo "== honeypot filled (expect 202) =="
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/public/submissions" \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
  -d "{\"widget_id\":\"$WID\",\"fields\":{\"email\":\"bot@spam.example\"},\"website\":\"http://junk.example\"}"

echo "== burst until window cap (expect 201s then 429) =="
for _ in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w '%{http_code} ' -X POST "$BASE/api/v1/public/submissions" \
    -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
    -d "{\"widget_id\":\"$WID\",\"fields\":{\"email\":\"burst@example.com\"}}"
done
echo

sleep 1
echo "== stored rows (geo enrichment proof) =="
docker exec widget-platform-db psql -U widget -d widget_platform \
  -c "SELECT country, city, region, payload->>'email' AS email FROM submissions ORDER BY created_at DESC LIMIT 4;"

echo "== outbox jobs (side effect queued) =="
docker exec widget-platform-db psql -U widget -d widget_platform \
  -c "SELECT type, status, attempts FROM jobs ORDER BY id DESC LIMIT 4;"

echo "== worker mail log lines =="
grep 'fake email' /tmp/gate_uvicorn.log | head -2 || echo "(none yet)"

kill $SERVER_PID 2>/dev/null || true
