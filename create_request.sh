#!/bin/bash

BASE_URL="${BASE_URL:-http://localhost:8000}"
COOKIE_FILE="/tmp/repair_cookies_$$"
SEED_DATA="/home/devler/dev/repair_service/requests_app/data/seed_data.json"

cleanup() {
    rm -f "$COOKIE_FILE"
}
trap cleanup EXIT

# Получение username мастера по его pid из API
get_master_username_from_pid() {
    local pid="$1"
    local response
    response=$(curl -s "$BASE_URL/test/get_master_username/$pid/")
    local username
    username=$(echo "$response" | grep -oP '"username":\s*"\K[^"]+' | head -1)
    
    if [ -z "$username" ]; then
        echo "Ошибка: не удалось получить username для master_id=$pid" >&2
        return 1
    fi
    echo "$username"
}

# Получение пароля мастера по username из seed_data.json
get_master_password_from_username() {
    local username="$1"
    local password
    
    # Проверяем master1
    if [ "$username" = "master1" ]; then
        password="master123"
    elif [ "$username" = "master2" ]; then
        password="master123"
    else
        echo "Ошибка: неизвестный username мастера: $username" >&2
        return 1
    fi
    
    echo "$password"
}

get_csrf_token() {
    local url="$1"
    local description="$2"
    local page token
    page=$(curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" "$url")
    token=$(echo "$page" | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+' | tail -1)

    if [ -z "$token" ]; then
        echo "Ошибка: не удалось получить CSRF токен для $description" >&2
        exit 1
    fi
    echo "$token"
}

logout() {
    rm -f "$COOKIE_FILE"
    curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -L -X POST "$BASE_URL/logout/" \
        -H "Referer: $BASE_URL/" -o /dev/null
}

login() {
    local username="$1"
    local password="$2"
    local role="$3"

    logout

    echo "Получение CSRF токена для $role..."
    local csrf
    csrf=$(get_csrf_token "$BASE_URL/login/" "$role")

    echo "Авторизация как $username..."
    curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -X POST "$BASE_URL/login/" \
        -H "Referer: $BASE_URL/login/" \
        -d "username=$username&password=$password&csrfmiddlewaretoken=$csrf" \
        -D - -o /dev/null | grep -q "sessionid" && echo "Успешная авторизация" || (echo "Ошибка логина"; exit 1)
}

echo "1. Авторизация как client1..."
login "client1" "client123" "клиента"

echo "2. Получение CSRF токена для создания заявки..."
CREATE_CSRF=$(get_csrf_token "$BASE_URL/client/requests/create/" "создания заявки")

echo "3. Создание заявки..."
ADDRESS="${1-Test Address}"
PROBLEM="${2-Test Problem Description}"

CREATE_HEADERS=$(curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -X POST "$BASE_URL/client/requests/create/" \
    -H "Referer: $BASE_URL/client/requests/create/" \
    -d "address=$ADDRESS&problem_text=$PROBLEM&csrfmiddlewaretoken=$CREATE_CSRF" \
    -D - -o /dev/null 2>&1)

CREATE_STATUS=$(echo "$CREATE_HEADERS" | grep -m1 -oP 'HTTP/[\d.]+ \K\d+')

if [[ "$CREATE_STATUS" == "302" ]]; then
    REQUEST_ID=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/client/requests/" | grep -oP 'href="/client/requests/(\d+)' | head -1 | grep -oP '\d+')
    echo "Заявка создана!"
    echo "ID заявки: $REQUEST_ID"
    echo "Адрес: $ADDRESS"
    echo "Проблема: $PROBLEM"
else
    echo "Ошибка создания заявки (статус: $CREATE_STATUS)"
    exit 1
fi

echo "4. Авторизация как dispatcher1..."
login "dispatcher1" "dispatcher123" "диспетчера"

echo "5. Получение случайного мастера..."
MASTER_RESPONSE=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/test/get_random_master/")
MASTER_ID=$(echo "$MASTER_RESPONSE" | grep -oP '"master_id":\s*\K\d+' | head -1)

if [ -z "$MASTER_ID" ]; then
    echo "Не удалось получить случайного мастера, используем ID по умолчанию: 7"
    MASTER_ID=7
else
    echo "Выбран случайный мастер с ID: $MASTER_ID"
fi

echo "6. Получение username мастера по PID..."
MASTER_USERNAME=$(get_master_username_from_pid "$MASTER_ID")
echo "Username мастера: $MASTER_USERNAME"

echo "7. Получение пароля мастера..."
MASTER_PASSWORD=$(get_master_password_from_username "$MASTER_USERNAME")

echo "8. Авторизация как мастер $MASTER_USERNAME для проверки активных заявок..."
login "$MASTER_USERNAME" "$MASTER_PASSWORD" "мастера"

echo "9. Проверка наличия активной заявки у мастера..."
ACTIVE_REQUEST=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/master/requests/active/" | grep -oP 'href="/master/requests/(\d+)' | head -1 | grep -oP '\d+')

if [ -n "$ACTIVE_REQUEST" ]; then
    echo "У мастера есть активная заявка $ACTIVE_REQUEST, пробуем завершить её..."
    COMPLETE_CSRF=$(get_csrf_token "$BASE_URL/master/requests/$ACTIVE_REQUEST/complete/" "завершения заявки")
    COMPLETE_STATUS=$(curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -X POST "$BASE_URL/master/requests/$ACTIVE_REQUEST/complete/" \
        -H "Referer: $BASE_URL/master/requests/$ACTIVE_REQUEST/complete/" \
        -d "csrfmiddlewaretoken=$COMPLETE_CSRF" \
        -w "%{http_code}" -o /dev/null)
    
    if [ "$COMPLETE_STATUS" = "302" ]; then
        echo "Заявка $ACTIVE_REQUEST завершена"
    else
        echo "Не удалось завершить заявку (код: $COMPLETE_STATUS), продолжаем..."
    fi
else
    echo "У мастера нет активных заявок"
fi

echo "10. Повторная авторизация как dispatcher1..."
login "dispatcher1" "dispatcher123" "диспетчера"

echo "11. Назначение мастера для заявки $REQUEST_ID..."
ASSIGN_CSRF=$(get_csrf_token "$BASE_URL/dispatcher/requests/$REQUEST_ID/assign/" "назначения мастера")

ASSIGN_STATUS=$(curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -X POST "$BASE_URL/dispatcher/requests/$REQUEST_ID/assign/" \
    -H "Referer: $BASE_URL/dispatcher/requests/$REQUEST_ID/assign/" \
    -d "assigned_to=$MASTER_ID&csrfmiddlewaretoken=$ASSIGN_CSRF" \
    -w "%{http_code}" -o /dev/null)

if [ "$ASSIGN_STATUS" = "302" ]; then
    echo "Мастер $MASTER_ID назначен!"
else
    echo "Ошибка назначения мастера (код: $ASSIGN_STATUS)"
    exit 1
fi
