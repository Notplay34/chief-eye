# Тесты API

Тестовый слой теперь изолирован: каждый тест поднимает свою временную SQLite-БД, создаёт схему и seed'ит тестового администратора. Внешний Postgres, `.env` и реальные `SUPERUSER_*` для прогонов не нужны.

Запуск:

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

Сценарии:

- `test_health.py` — проверка `GET /health`.
- `test_auth_and_orders.py` — логин, `/auth/me`, создание заказа, оплата, проверка платежей и строк кассы.
- `test_cash_and_warehouse.py` — смены, склад заготовок, резерв/списание, доплата за номера и выплата павильону 2.

Тестовый пользователь:

- логин: `admin`
- пароль: `admin1234`
- роль: `ROLE_ADMIN`

Если при запуске не хватает драйвера SQLite или HTTP-клиента для тестов, установи зависимости из `requirements.txt` ещё раз: туда добавлены `aiosqlite` и `httpx`.
