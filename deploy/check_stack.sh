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

SMOKE_LOGIN="__smoke_check__"
SMOKE_PASSWORD="$(openssl rand -base64 24 2>/dev/null | tr -d '\n' || date +%s_smoke_password)"

cleanup_smoke_user() {
  cd "$PROJECT_ROOT/backend" && "$PROJECT_ROOT/backend/.venv/bin/python" - <<'PY' >/dev/null 2>&1 || true
import asyncio

from sqlalchemy import select

from app.core.database import async_session_maker, engine
from app.models import Employee


async def main() -> None:
    async with async_session_maker() as session:
        employee = (
            await session.execute(select(Employee).where(Employee.login_normalized == "__smoke_check__"))
        ).scalar_one_or_none()
        if employee is not None:
            employee.is_active = False
            session.add(employee)
            await session.commit()
    await engine.dispose()


asyncio.run(main())
PY
}
trap cleanup_smoke_user EXIT

echo "== health напрямую =="
curl -fsS http://127.0.0.1:8000/health
echo

echo "== service user =="
SERVICE_USER="$(systemctl show -p User --value eye_w)"
if [ "$SERVICE_USER" = "root" ] || [ -z "$SERVICE_USER" ]; then
  echo "Сервис eye_w не должен работать от root"
  exit 1
fi
echo "$SERVICE_USER"

echo "== health через nginx =="
curl -fsS http://127.0.0.1/health
echo

echo "== prepare smoke login =="
cd "$PROJECT_ROOT/backend" && "$PROJECT_ROOT/backend/.venv/bin/python" - <<PY
import asyncio

from sqlalchemy import select

from app.core.database import async_session_maker, engine
from app.models import Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import hash_password


async def main() -> None:
    async with async_session_maker() as session:
        employee = (
            await session.execute(select(Employee).where(Employee.login_normalized == "$SMOKE_LOGIN"))
        ).scalar_one_or_none()
        if employee is None:
            employee = Employee(
                name="Smoke Check",
                role=EmployeeRole.ROLE_ADMIN,
                login="$SMOKE_LOGIN",
                is_active=True,
            )
        employee.role = EmployeeRole.ROLE_ADMIN
        employee.password_hash = hash_password("$SMOKE_PASSWORD")
        employee.is_active = True
        session.add(employee)
        await session.commit()
    await engine.dispose()


asyncio.run(main())
PY

echo "== login =="
TOKEN=$(curl -fsS -X POST http://127.0.0.1:8000/auth/login \
  --data-urlencode "username=$SMOKE_LOGIN" \
  --data-urlencode "password=$SMOKE_PASSWORD" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "Не удалось получить токен через /auth/login"
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
