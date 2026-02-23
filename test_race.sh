#!/bin/bash

BASE_URL="${BASE_URL:-http://localhost:8000}"

cleanup() {
    rm -f /tmp/race_test_*.txt /tmp/race_master_cookies_* /tmp/repair_cookies_*
}
trap cleanup EXIT

SCRIPT_PID=$$

get_csrf_token() {
    local cookie_file="$1"
    local url="$2"
    local description="$3"
    local page token
    page=$(curl -s -c "$cookie_file" -b "$cookie_file" "$url")
    token=$(echo "$page" | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+' | tail -1)

    if [ -z "$token" ]; then
        echo "Error: Failed to get CSRF token for $description" >&2
        return 1
    fi
    echo "$token"
}

logout() {
    local cookie_file="$1"
    curl -s -c "$cookie_file" -b "$cookie_file" -L -X POST "$BASE_URL/logout/" \
        -H "Referer: $BASE_URL/" -o /dev/null
}

login() {
    local cookie_file="$1"
    local username="$2"
    local password="$3"
    local role="$4"

    logout "$cookie_file"

    local csrf
    csrf=$(get_csrf_token "$cookie_file" "$BASE_URL/login/" "$role")
    if [ -z "$csrf" ]; then
        echo "Failed to get CSRF for login" >&2
        return 1
    fi

    curl -s -c "$cookie_file" -b "$cookie_file" -X POST "$BASE_URL/login/" \
        -H "Referer: $BASE_URL/login/" \
        -d "username=$username&password=$password&csrfmiddlewaretoken=$csrf" \
        -D - -o /dev/null | grep -q "sessionid" && echo "Logged in as $username" || (echo "Login failed"; exit 1)
}

echo "=== Race Condition Test for 'Take Request to Work' ==="
echo ""

# Check if REQUEST_ID provided as argument, otherwise create one
if [ -n "$1" ]; then
    REQUEST_ID="$1"
    echo "Using provided request ID: $REQUEST_ID"
else
    echo "Creating test request directly in database..."
    REQUEST_OUTPUT=$(docker compose exec web python manage.py shell -c "
from requests_app.models import Request, User
client = User.objects.filter(role='client').first()
master = User.objects.filter(role='master', id=6).first()
r = Request.objects.create(
    address='Race Test',
    problem_text='Race condition test',
    client=client,
    assigned_to=master,
    status='assigned'
)
print(r.id)
")
    REQUEST_ID=$(echo "$REQUEST_OUTPUT" | tail -1)
    echo "Created request ID: $REQUEST_ID"
fi

echo "Request ID for test: $REQUEST_ID"
echo ""

echo "=== Step 1: Verify request is assigned to master ==="
MASTER_USERNAME="master1"
MASTER_PASSWORD="master123"

echo ""
echo "=== Step 2: Run parallel race test for taking request to work ==="
echo "Starting 3 parallel requests to /master/requests/$REQUEST_ID/start/"

for i in 1 2 3; do
    MASTER_COOKIE="/tmp/race_master_cookies_${SCRIPT_PID}_$i"
    login "$MASTER_COOKIE" "$MASTER_USERNAME" "$MASTER_PASSWORD" "master"
    
    START_URL="$BASE_URL/master/requests/$REQUEST_ID/start/"
    START_CSRF=$(get_csrf_token "$MASTER_COOKIE" "$START_URL" "start work")
    
    if [ -z "$START_CSRF" ]; then
        echo "Request $i: Failed to get CSRF token"
        echo "HTTP 403" > "/tmp/race_result_$i.txt"
    else
        curl -s -c "$MASTER_COOKIE" -b "$MASTER_COOKIE" \
            -X POST "$START_URL" \
            -H "Referer: $START_URL" \
            -d "csrfmiddlewaretoken=$START_CSRF" \
            -w "\nHTTP Status: %{http_code}\n" -o "/tmp/race_result_$i.txt" &
    fi
done

wait

echo ""
echo "=== Results ==="
for i in 1 2 3; do
    echo "--- Request $i ---"
    cat "/tmp/race_result_$i.txt" | head -20
done

echo ""
echo "=== Final request status ==="
docker compose exec web python manage.py shell -c "
from requests_app.models import Request
r = Request.objects.get(id=$REQUEST_ID)
print(f'Request {$REQUEST_ID}: status={r.status}')
"
