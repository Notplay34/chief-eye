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

echo "== auth token =="
TOKEN=$(cd "$PROJECT_ROOT/backend" && "$PROJECT_ROOT/backend/.venv/bin/python" - <<'PY'
import asyncio
import sys

from sqlalchemy import select

from app.config import settings
from app.core.database import async_session_maker, engine
from app.core.identity import normalize_login
from app.models import Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import create_access_token


async def main() -> int:
    login = normalize_login(settings.superuser_login)
    async with async_session_maker() as session:
        query = select(Employee).where(
            Employee.is_active == True,
            Employee.role == EmployeeRole.ROLE_ADMIN,
        )
        if login:
            preferred = (
                await session.execute(query.where(Employee.login_normalized == login).order_by(Employee.id))
            ).scalars().first()
            if preferred is not None:
                employee = preferred
            else:
                employee = (await session.execute(query.order_by(Employee.id))).scalars().first()
        else:
            employee = (await session.execute(query.order_by(Employee.id))).scalars().first()

    await engine.dispose()
    if employee is None:
        print("Активный администратор не найден", file=sys.stderr)
        return 1

    print(create_access_token(employee.id, employee.role.value, employee.name, employee.login or ""))
    return 0


raise SystemExit(asyncio.run(main()))
PY
)

if [ -z "$TOKEN" ]; then
  echo "Не удалось получить сервисный smoke-токен"
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
