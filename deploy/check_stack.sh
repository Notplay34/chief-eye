#!/bin/bash
# Быстрая smoke-проверка прод-стека после деплоя.
# Запуск: bash deploy/check_stack.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "backend/.env не найден"
  exit 1
fi

source "$ENV_FILE"

LOGIN="${SUPERUSER_LOGIN:-}"
PASSWORD="${SUPERUSER_PASSWORD:-}"

if [ -z "$LOGIN" ] || [ -z "$PASSWORD" ]; then
  echo "В backend/.env должны быть SUPERUSER_LOGIN и SUPERUSER_PASSWORD"
  exit 1
fi

echo "== health напрямую =="
curl -fsS http://127.0.0.1:8000/health
echo

echo "== health через nginx =="
curl -fsS http://127.0.0.1/health
echo

echo "== login =="
TOKEN=$(curl -fsS -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$LOGIN&password=$PASSWORD" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "Не удалось получить токен"
  exit 1
fi

echo "== auth/me через backend =="
curl -fsS http://127.0.0.1:8000/auth/me -H "Authorization: Bearer $TOKEN"
echo

echo "== auth/me через nginx =="
curl -fsS http://127.0.0.1/auth/me -H "Authorization: Bearer $TOKEN"
echo

echo "== analytics через nginx =="
curl -fsS "http://127.0.0.1/analytics/dashboard?period=month" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "OK"

echo "== static frontend =="
curl -fsS http://127.0.0.1/login.html >/dev/null
curl -fsS http://127.0.0.1/analytics-docs.html >/dev/null
echo "OK"

echo "Smoke-check завершён"
