# Установка и первый запуск

Актуальная инструкция для локального запуска и первоначальной настройки.

## 1. Требования

- Python 3.11+
- PostgreSQL
- nginx нужен только для серверного деплоя

## 2. База данных

Создайте БД и пользователя, затем подготовьте `backend/.env`:

```bash
cd backend
cp .env.example .env
```

Минимальный пример:

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w
JWT_SECRET=
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=admin1234
SUPERUSER_NAME=Администратор
```

Это пример для локального запуска. Реальные production-секреты нельзя коммитить в репозиторий.

## 3. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Проверка:

```bash
curl http://127.0.0.1:8000/health
```

## 4. Frontend

```bash
cd frontend
python3 -m http.server 8080
```

Открыть:

- `http://127.0.0.1:8080/login.html`

## 5. Первый вход

Если в `backend/.env` заданы все `SUPERUSER_*`, стартовый администратор создаётся автоматически при старте backend.

После первого входа пароль нужно сменить в интерфейсе.

## 6. Локальная проверка

Перед использованием прогонять:

```bash
python3 -m pytest backend/tests -q
python3 -m compileall backend/app
node --check frontend/*.js frontend/form-page/*.js
```

Если нужна полная серверная smoke-проверка, использовать `docs/SMOKE_TEST.md` и `deploy/check_stack.sh`.

## 7. Если нужен сервер

Для nginx, systemd и пост-деплойной проверки использовать [DEPLOYMENT.md](DEPLOYMENT.md).
