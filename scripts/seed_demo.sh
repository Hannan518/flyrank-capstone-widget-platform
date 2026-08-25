#!/usr/bin/env bash
# Seeds demo data through the public API so an evaluator (or a human) gets a
# ready-to-click dashboard after `docker compose up`.
#
#   BASE_URL=http://localhost:8000 scripts/seed_demo.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
PY="${PYTHON:-python3}"

EMAIL="demo-owner@example.com"
PASSWORD="demo-password-1"

echo "Seeding demo data against $BASE ..."

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

if [ "$(code -X POST "$BASE/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")" = "201" ]; then
  echo "registered $EMAIL"
else
  echo "$EMAIL already registered; continuing"
fi

TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

make_widget() { # name title origin
  curl -s -X POST "$BASE/api/v1/widgets" \
    -H "$AUTH" -H 'Content-Type: application/json' \
    -d "{
      \"type\":\"signup_form\",
      \"title\":\"$2\",
      \"description\":\"Demo widget seeded by scripts/seed_demo.sh\",
      \"fields\":[{\"name\":\"email\",\"label\":\"Email\",\"type\":\"email\",\"required\":true}],
      \"button_text\":\"Subscribe\",
      \"allowed_origins\":[\"http://localhost:5500\"]
    }" | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["id"])'
}

NEWSLETTER=$(make_widget newsletter "Join the newsletter")
CTA=$(make_widget cta "Get early access")
echo "widgets: $NEWSLETTER $CTA"

seed_submission() { # widget email key
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/v1/public/submissions" \
    -H 'Content-Type: application/json' -H 'Origin: http://localhost:5500' \
    -d "{\"widget_id\":\"$1\",\"fields\":{\"email\":\"$2\"},\"idempotency_key\":\"$3\"}"
}

i=0
for who in alice bob carol dave erin; do
  i=$((i + 1))
  if [ $((i % 2)) -eq 0 ]; then WIDGET="$CTA"; else WIDGET="$NEWSLETTER"; fi
  STATUS=$(seed_submission "$WIDGET" "$who@example.com" "$("$PY" -c 'import uuid; print(uuid.uuid4())')")
  echo "submission $who -> $STATUS"
done

TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

cat <<EOF

Seed complete.
  owner:    $EMAIL / $PASSWORD
  widgets:  newsletter=$NEWSLETTER  cta=$CTA
  try:      paste this on any page served from http://localhost:5500:
              <script src="$BASE/widget.v1.js?id=$NEWSLETTER"></script>
EOF

echo "dashboard stats after seeding:"
curl -s "$BASE/api/v1/dashboard/stats?days=30" -H "Authorization: Bearer $TOKEN"
echo
