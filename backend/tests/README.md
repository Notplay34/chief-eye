# Тесты API

Запуск (из папки `backend`, с установленными зависимостями):

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

- **test_health.py** — проверка `GET /health` (не требует БД).
- **test_auth_and_orders.py** — логин, `/auth/me`, создание заказа и оплата. Требуют запущенную БД и суперпользователя (логин/пароль из `.env` или переменных `SUPERUSER_LOGIN`, `SUPERUSER_PASSWORD`). При отсутствии БД или неверных данных тесты с авторизацией помечаются как skipped.

Только health без БД:

```bash
python -m pytest tests/test_health.py -v
```
