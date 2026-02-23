# Commands

## Initial users

```bash
docker compose exec web python manage.py create_initial_users
```

Creates:
- Superuser (from ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD in .env) - **do NOT use for testing**
- Test users (use ONLY these for testing):

| Username | Password | Role       |
|----------|----------|------------|
| testuser | testuser123 | client   |
| client1  | client123   | client    |
| client2  | client123   | client    |
| client3  | client123   | client    |
| dispatcher1 | dispatcher123 | dispatcher |
| master1  | master123   | master    |
| master2  | master123   | master    |

**Important:** Always use test users for testing. Do not use superuser account.

## Docker Compose

All commands run inside the web container using `docker compose exec web`.

```bash
# Run management command
docker compose exec web python manage.py <command>

# Check running containers
docker compose ps

# View logs
docker compose logs -f web
```

## Login to application (curl)

When testing features that require authenticated user, use curl with CSRF token:

```bash
# 1. Get CSRF token and session cookie
CSRF=$(curl -s -c /tmp/cookies.txt http://localhost:8000/login/ | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+')

# 2. Login with test user
curl -s -c /tmp/cookies.txt -X POST "http://localhost:8000/login/" \
  -H "Referer: http://localhost:8000/login/" \
  -d "username=client1&password=client123&csrfmiddlewaretoken=$CSRF" \
  -L -o /dev/null -w "%{http_code}"

# 3. Use authenticated session
curl -s -b /tmp/cookies.txt http://localhost:8000/client/requests/
```
