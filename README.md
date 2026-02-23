# repair_service

## Тестирование race condition (гонки)

При параллельных запросах "Взять в работу" только один запрос должен успешно обработать заявку, остальные должны получить отказ.

### Автоматический тест

```bash
# Создать заявку и запустить тест
bash test_race.sh

# Или указать конкретный ID заявки (заявка должна быть в статусе 'assigned')
bash test_race.sh 61
```

Скрипт:
1. Создаёт заявку с назначенным мастером (или использует указанную)
2. Запускает 3 параллельных запроса к `/master/requests/<id>/start/`
3. Выводит результаты: первый запрос получает HTTP 302 (успех), остальные — HTTP 200 (отказ)

### Ручная проверка (два терминала)

**Терминал 1 — Создание заявки:**

```bash
# Логин как диспетчер
CSRF=$(curl -s -c /tmp/cookies.txt http://localhost:8000/login/ | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+')
curl -s -c /tmp/cookies.txt -X POST "http://localhost:8000/login/" \
  -H "Referer: http://localhost:8000/login/" \
  -d "username=dispatcher1&password=dispatcher123&csrfmiddlewaretoken=$CSRF" -L -o /dev/null

# Создать заявку
CSRF=$(curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt http://localhost:8000/client/requests/create/ | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+')
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST "http://localhost:8000/client/requests/create/" \
  -H "Referer: http://localhost:8000/client/requests/create/" \
  -d "address=Test&problem_text=Test&csrfmiddlewaretoken=$CSRF" -o /dev/null

# Назначить мастера (master1, ID=6)
# Сначала получить страницу назначения для получения CSRF
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt "http://localhost:8000/dispatcher/requests/1/assign/" > /tmp/assign.html
CSRF=$(grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+' /tmp/assign.html | tail -1)
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST "http://localhost:8000/dispatcher/requests/1/assign/" \
  -H "Referer: http://localhost:8000/dispatcher/requests/1/assign/" \
  -d "assigned_to=6&csrfmiddlewaretoken=$CSRF" -o /dev/null
```

**Терминал 2 и 3 — Подготовка параллельных запросов:**

Подготовьте 2-3 curl команды (НЕ выполняйте):

```bash
# Мастер 1 логинится
CSRF=$(curl -s -c /tmp/m1.txt http://localhost:8000/login/ | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+')
curl -s -c /tmp/m1.txt -X POST "http://localhost:8000/login/" \
  -d "username=master1&password=master123&csrfmiddlewaretoken=$CSRF" -L -o /dev/null

# Получить CSRF для страницы "взять в работу"
CSRF=$(curl -s -c /tmp/m1.txt -b /tmp/m1.txt http://localhost:8000/master/requests/1/start/ | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+')

# Выполнить POST (каждая команда в отдельном терминале):
curl -s -c /tmp/m1.txt -b /tmp/m1.txt -X POST "http://localhost:8000/master/requests/1/start/" \
  -d "csrfmiddlewaretoken=$CSRF" -w "Request 1: %{http_code}\n" -o /dev/null
```

**Выполните все POST запросы одновременно** (практически одновременно, в идеале используя фоновые процессы).

### Ожидаемый результат

- Ровно один из запросов: HTTP 302 (редирект — успешно взято в работу)
- Остальные запросы: HTTP 200 (форма с ошибкой — заявка уже в работе)
- Финальный статус заявки: `in_progress`

### Реализация

Логика защиты от race condition находится в:
- `requests_app/views/master.py:104` — `RequestStartWorkView`
- `requests_app/services/request_service.py` — метод `start_work()` использует `select_for_update()` для блокировки заявки при изменении статуса
