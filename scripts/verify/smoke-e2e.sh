#!/bin/bash
set -e

# PLOS Production Smoke Test
# Runs auth + journal + reporting checks through the API gateway.

BASE_URL="${1:-http://localhost:8000/api/v1}"
TODAY="$(date +%Y-%m-%d)"

declare -a RESULT_NAMES
declare -a RESULT_STATUSES
declare -a RESULT_DETAILS

add_result() {
    local name="$1"
    local status="$2"
    local detail="${3:-}"
    RESULT_NAMES+=("$name")
    RESULT_STATUSES+=("$status")
    RESULT_DETAILS+=("$detail")
}

# expect_error NAME CURL_ARGS... -- expected status label
# Calls curl; if the response is an HTTP error (>=400) -> OK, else FAIL.
expect_error() {
    local name="$1"
    local expected="$2"
    shift 2
    local resp
    resp=$(curl -s -w "\n%{http_code}" "$@" 2>/dev/null || true)
    local code
    code=$(echo "$resp" | tail -n1)
    if [ "$code" -ge 400 ] 2>/dev/null; then
        add_result "$name" "OK" "$expected expected"
    else
        add_result "$name" "FAIL" "expected $expected, got $code"
    fi
}

http_post() {
    local url="$1"
    local data="$2"
    shift 2
    local resp
    resp=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" "$@" -d "$data" "$url" 2>/dev/null || true)
    HTTP_CODE=$(echo "$resp" | tail -n1)
    BODY=$(echo "$resp" | sed '$d')
}

http_get() {
    local url="$1"
    shift
    local resp
    resp=$(curl -s -w "\n%{http_code}" "$@" "$url" 2>/dev/null || true)
    HTTP_CODE=$(echo "$resp" | tail -n1)
    BODY=$(echo "$resp" | sed '$d')
}

print_results() {
    printf "\n%-40s %-8s %s\n" "NAME" "STATUS" "DETAIL"
    printf "%-40s %-8s %s\n" "----" "------" "------"
    for i in "${!RESULT_NAMES[@]}"; do
        printf "%-40s %-8s %s\n" "${RESULT_NAMES[$i]}" "${RESULT_STATUSES[$i]}" "${RESULT_DETAILS[$i]}"
    done
    echo ""
}

EMAIL="e2e+$(tr -d '-' < /proc/sys/kernel/random/uuid)@example.com"
USERNAME="user$((RANDOM % 9000 + 1000))"
PASSWORD="TestPass123!"
TOKEN=""

# -- auth.register --
REGISTER_BODY="{\"email\":\"$EMAIL\",\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\",\"full_name\":\"E2E User\",\"timezone\":\"UTC\"}"

http_post "$BASE_URL/auth/register" "$REGISTER_BODY"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    add_result "auth.register" "OK" "user=$EMAIL"
else
    add_result "auth.register" "FAIL" "HTTP $HTTP_CODE"
fi

# -- auth.register.duplicate --
expect_error "auth.register.duplicate" "400" \
    -X POST -H "Content-Type: application/json" -d "$REGISTER_BODY" "$BASE_URL/auth/register"

# -- auth.login --
LOGIN_BODY="{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
http_post "$BASE_URL/auth/login" "$LOGIN_BODY"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    add_result "auth.login" "OK" "token_received"
else
    add_result "auth.login" "FAIL" "HTTP $HTTP_CODE"
fi

# -- auth.login.invalid --
BAD_LOGIN="{\"email\":\"$EMAIL\",\"password\":\"WrongPass123!\"}"
expect_error "auth.login.invalid" "401" \
    -X POST -H "Content-Type: application/json" -d "$BAD_LOGIN" "$BASE_URL/auth/login"

# -- journal.process.no_token (expect 401) --
expect_error "journal.process.no_token" "401" \
    -X POST "$BASE_URL/journal/process"

# -- auth.verify_token --
HEADERS=(-H "Authorization: Bearer $TOKEN")
http_post "$BASE_URL/auth/verify-token" "" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    add_result "auth.verify_token" "OK"
else
    add_result "auth.verify_token" "FAIL" "HTTP $HTTP_CODE"
fi

# -- journal.metrics --
http_get "$BASE_URL/journal/metrics"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    add_result "journal.metrics" "OK"
else
    add_result "journal.metrics" "FAIL" "HTTP $HTTP_CODE"
fi

# -- journal.process --
JOURNAL_BODY="{\"entry_text\":\"Slept 6 hours. Worked 3 hours. Drank 2 liters of water.\",\"entry_date\":\"$TODAY\",\"detect_gaps\":false,\"require_complete\":false}"
http_post "$BASE_URL/journal/process" "$JOURNAL_BODY" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    add_result "journal.process" "OK"
else
    add_result "journal.process" "FAIL" "HTTP $HTTP_CODE"
fi

# -- journal.process.empty (422) --
expect_error "journal.process.empty" "422" \
    -X POST -H "Content-Type: application/json" "${HEADERS[@]}" \
    -d '{"entry_text":""}' "$BASE_URL/journal/process"

# -- journal.process.too_long (422) --
TOO_LONG=$(python3 -c "print('a'*10001)")
expect_error "journal.process.too_long" "422" \
    -X POST -H "Content-Type: application/json" "${HEADERS[@]}" \
    -d "{\"entry_text\":\"$TOO_LONG\"}" "$BASE_URL/journal/process"

# -- journal.process.bad_date (422) --
expect_error "journal.process.bad_date" "422" \
    -X POST -H "Content-Type: application/json" "${HEADERS[@]}" \
    -d '{"entry_text":"test","entry_date":"2025-13-40"}' "$BASE_URL/journal/process"

# -- reports.weekly_overview --
http_get "$BASE_URL/journal/reports/weekly-overview" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    add_result "reports.weekly_overview" "OK"
else
    add_result "reports.weekly_overview" "FAIL" "HTTP $HTTP_CODE"
fi

# -- reports.daily_overview --
http_get "$BASE_URL/journal/reports/daily-overview?target_date=$TODAY" "${HEADERS[@]}"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    add_result "reports.daily_overview" "OK"
else
    add_result "reports.daily_overview" "FAIL" "HTTP $HTTP_CODE"
fi

# -- reports.weekly.invalid_days (422) --
expect_error "reports.weekly.invalid_days" "422" \
    "${HEADERS[@]}" "$BASE_URL/journal/reports/weekly-overview?days=0"

# -- reports.monthly.invalid_month (400) --
expect_error "reports.monthly.invalid_month" "400" \
    "${HEADERS[@]}" "$BASE_URL/journal/reports/monthly-overview?year=2025&month=0"

# -- reports.range.invalid (400) --
expect_error "reports.range.invalid" "400" \
    "${HEADERS[@]}" "$BASE_URL/journal/reports/range-overview?start_date=2025-01-10&end_date=2025-01-01"

# -- journal.resolve_gap.invalid_id (422) --
expect_error "journal.resolve_gap.invalid_id" "422" \
    -X POST -H "Content-Type: application/json" "${HEADERS[@]}" \
    -d '{"gap_id":"not-a-uuid","user_response":"ok"}' "$BASE_URL/journal/resolve-gap"

# -- Print results --
print_results

FAILS=0
for s in "${RESULT_STATUSES[@]}"; do
    [ "$s" = "FAIL" ] && FAILS=$((FAILS + 1))
done

if [ "$FAILS" -gt 0 ]; then
    exit 1
fi

exit 0
