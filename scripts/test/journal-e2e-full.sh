#!/bin/bash
set -e

# Journal E2E Full Test
# Exercises auth, journal processing, gap resolution, paragraph resolution,
# reporting endpoints enumerated from OpenAPI, and DB validation.

BASE="${BASE_URL:-http://localhost:8000/api/v1}"
DIRECT="${DIRECT_URL:-http://localhost:8002}"
TODAY="$(date +%Y-%m-%d)"
YEAR="$(date +%Y)"
MONTH="$(date +%-m)"
PASSWORD="TestPass123!"

# Results tracking
declare -a RESULT_NAMES
declare -a RESULT_STATUSES
declare -a RESULT_DETAILS

add_res() {
    local name="$1"
    local ok="$2"
    local detail="${3:-}"
    RESULT_NAMES+=("$name")
    if [ "$ok" = "true" ]; then
        RESULT_STATUSES+=("OK")
    else
        RESULT_STATUSES+=("FAIL")
    fi
    RESULT_DETAILS+=("$detail")
}

print_results() {
    printf "\n%-40s %-8s %s\n" "NAME" "STATUS" "DETAIL"
    printf "%-40s %-8s %s\n" "----" "------" "------"
    for i in "${!RESULT_NAMES[@]}"; do
        printf "%-40s %-8s %s\n" "${RESULT_NAMES[$i]}" "${RESULT_STATUSES[$i]}" "${RESULT_DETAILS[$i]}"
    done
    echo ""
}

# Helper: HTTP request returning body. Sets HTTP_CODE.
http_get() {
    local url="$1"
    shift
    local resp
    resp=$(curl -s -w "\n%{http_code}" "$@" "$url")
    HTTP_CODE=$(echo "$resp" | tail -n1)
    BODY=$(echo "$resp" | sed '$d')
}

http_post() {
    local url="$1"
    local data="$2"
    shift 2
    local resp
    resp=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" "$@" -d "$data" "$url")
    HTTP_CODE=$(echo "$resp" | tail -n1)
    BODY=$(echo "$resp" | sed '$d')
}

TOKEN=""
HEADERS=()
EXTRACTION_ID1=""
EXTRACTION_ID2=""

# -- auth.register --
EMAIL="e2efull+$(cat /proc/sys/kernel/random/uuid | tr -d '-')@example.com"
USERNAME="e2e$((RANDOM % 9000 + 1000))"

REGISTER_BODY=$(cat <<EOF
{"email":"$EMAIL","username":"$USERNAME","password":"$PASSWORD","full_name":"Journal E2E","timezone":"UTC"}
EOF
)

http_post "$BASE/auth/register" "$REGISTER_BODY"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    HEADERS=(-H "Authorization: Bearer $TOKEN")
    add_res "auth.register" "true" "$EMAIL"
else
    add_res "auth.register" "false" "HTTP $HTTP_CODE"
fi

# -- journal.process.valid --
PROCESS_BODY=$(cat <<EOF
{"entry_text":"Slept 7 hours. Walked 5000 steps. Drank 1.5 liters water. Mood 8.","entry_date":"$TODAY","detect_gaps":false,"require_complete":false}
EOF
)

http_post "$BASE/journal/process" "$PROCESS_BODY" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    EXTRACTION_ID1=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entry_id',''))" 2>/dev/null || true)
    add_res "journal.process.valid" "true" "$EXTRACTION_ID1"
else
    add_res "journal.process.valid" "false" "HTTP $HTTP_CODE"
fi

# -- journal.process.gaps --
GAPS_BODY=$(cat <<EOF
{"entry_text":"Yesterday was weird, had stuff, met someone, did some work, ate something.","entry_date":"$TODAY","detect_gaps":true,"require_complete":false}
EOF
)

http_post "$BASE/journal/process" "$GAPS_BODY" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    EXTRACTION_ID2=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entry_id',''))" 2>/dev/null || true)
    GAP_COUNT=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('clarification_questions',[])))" 2>/dev/null || echo "0")
    add_res "journal.process.gaps" "true" "entry=$EXTRACTION_ID2 gaps=$GAP_COUNT"
else
    add_res "journal.process.gaps" "false" "HTTP $HTTP_CODE"
fi

# -- journal.pending-gaps --
http_get "$BASE/journal/pending-gaps" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    PENDING_COUNT=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
    add_res "journal.pending-gaps" "true" "count=$PENDING_COUNT"

    if [ "$PENDING_COUNT" -gt 0 ]; then
        GAP_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('gap_id',''))" 2>/dev/null || true)
        RESOLVE_BODY="{\"gap_id\":\"$GAP_ID\",\"user_response\":\"It was a 30 minute run in the morning.\"}"
        http_post "$BASE/journal/resolve-gap" "$RESOLVE_BODY" "${HEADERS[@]}"
        if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
            add_res "journal.resolve-gap" "true" "$GAP_ID"
        else
            add_res "journal.resolve-gap" "false" "HTTP $HTTP_CODE"
        fi
    else
        add_res "journal.resolve-gap" "true" "no pending gaps"
    fi
else
    add_res "journal.pending-gaps" "false" "HTTP $HTTP_CODE"
fi

# -- journal.resolve-paragraph --
if [ -n "$EXTRACTION_ID2" ]; then
    PARA_BODY="{\"entry_id\":\"$EXTRACTION_ID2\",\"user_paragraph\":\"The activity was badminton for 45 minutes at 7am. Breakfast was idli and coffee.\"}"
    http_post "$BASE/journal/resolve-paragraph" "$PARA_BODY" "${HEADERS[@]}"
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        add_res "journal.resolve-paragraph" "true" "$EXTRACTION_ID2"
    else
        add_res "journal.resolve-paragraph" "false" "HTTP $HTTP_CODE"
    fi
else
    add_res "journal.resolve-paragraph" "false" "missing extraction id"
fi

# -- journal GET endpoints --
for path in /journal/activities /journal/activity-summary /journal/health /journal/metrics; do
    http_get "$BASE$path" "${HEADERS[@]}"
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        add_res "journal$path" "true"
    else
        add_res "journal$path" "false" "HTTP $HTTP_CODE"
    fi
done

# -- reporting endpoints from openapi --
SPEC=""
http_get "$DIRECT/openapi.json"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    SPEC="$BODY"

    # Extract report paths and build query strings using python3
    REPORT_URLS=$(echo "$SPEC" | python3 -c "
import sys, json

spec = json.load(sys.stdin)
today = '$TODAY'
year = '$YEAR'
month = '$MONTH'

paths = sorted(p for p in spec.get('paths', {}) if p.startswith('/journal/reports/'))

for path in paths:
    op = spec['paths'][path].get('get')
    if not op:
        continue
    params = {}
    for param in (op.get('parameters') or []):
        if param.get('in') != 'query':
            continue
        name = param['name']
        if name == 'target_date':
            params[name] = today
        elif name == 'start_date':
            params[name] = today
        elif name == 'end_date':
            params[name] = today
        elif name == 'year':
            params[name] = year
        elif name == 'month':
            params[name] = month
        elif name == 'bucket':
            params[name] = 'day'
        elif name == 'days':
            params[name] = '7'
        elif param.get('required'):
            params[name] = '1'
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    if qs:
        qs = '?' + qs
    print(f'{path}|{qs}')
" 2>/dev/null || true)

    while IFS='|' read -r rpath query; do
        [ -z "$rpath" ] && continue
        http_get "$BASE${rpath}${query}" "${HEADERS[@]}"
        if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
            add_res "report$rpath" "true" "$query"
        else
            add_res "report$rpath" "false" "HTTP $HTTP_CODE"
        fi
    done <<< "$REPORT_URLS"
else
    add_res "report.openapi.enumeration" "false" "HTTP $HTTP_CODE"
fi

# -- DB validation --
if command -v docker &>/dev/null; then
    UID_VAL=$(docker exec plos-supabase-db psql -U postgres -d plos -t -A -c \
        "SELECT id FROM users WHERE email = '$EMAIL' LIMIT 1;" 2>/dev/null | tr -d '[:space:]')
    if [ -n "$UID_VAL" ]; then
        add_res "db.user.lookup" "true" "$UID_VAL"
    else
        add_res "db.user.lookup" "false" "user not found"
    fi

    if [ -n "$EXTRACTION_ID1" ]; then
        DB_QUERY="SELECT 'journal_extractions' AS table_name, COUNT(*) FROM journal_extractions WHERE id = '$EXTRACTION_ID1'
UNION ALL SELECT 'extraction_metrics', COUNT(*) FROM extraction_metrics WHERE extraction_id = '$EXTRACTION_ID1'
UNION ALL SELECT 'extraction_activities', COUNT(*) FROM extraction_activities WHERE extraction_id = '$EXTRACTION_ID1'
UNION ALL SELECT 'extraction_consumptions', COUNT(*) FROM extraction_consumptions WHERE extraction_id = '$EXTRACTION_ID1'
UNION ALL SELECT 'extraction_sleep', COUNT(*) FROM extraction_sleep WHERE extraction_id = '$EXTRACTION_ID1'
UNION ALL SELECT 'journal_timeseries', COUNT(*) FROM journal_timeseries WHERE extraction_id = '$EXTRACTION_ID1';"

        DB_OUT=$(docker exec plos-supabase-db psql -U postgres -d plos -t -A -F ',' -c "$DB_QUERY" 2>/dev/null || true)
        add_res "db.extraction.rows" "true" "$DB_OUT"
    fi
else
    add_res "db.validation" "false" "docker not found"
fi

# -- Print results table --
print_results

TOTAL=${#RESULT_NAMES[@]}
FAILS=0
for s in "${RESULT_STATUSES[@]}"; do
    [ "$s" = "FAIL" ] && FAILS=$((FAILS + 1))
done

echo "TOTAL=$TOTAL FAILS=$FAILS"

if [ "$FAILS" -gt 0 ]; then
    exit 1
fi

exit 0
