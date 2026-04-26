# Техническая документация

Этот документ является единственным техническим runbook'ом проекта: локальный запуск, структура, миграции, деплой, бэкапы, проверки и безопасность.

## Структура репозитория

| Путь | Назначение |
|------|------------|
| `backend/` | FastAPI backend, модели, API, сервисы и тесты |
| `frontend/` | Статические страницы, общие скрипты и стили |
| `frontend/form-page/` | JS-модули формы оформления документов |
| `templates/` | `.docx` шаблоны документов |
| `alembic/` | Миграции PostgreSQL |
| `deploy/` | nginx-конфиг, setup, backup и server smoke |
| `scripts/` | Локальные release-проверки |
| `docs/` | Два поддерживаемых документа: проектный и технический |

## Backend

Стек:

- `FastAPI`
- `SQLAlchemy`
- `PostgreSQL`
- `Alembic`
- `pytest`

Основные пакеты:

- `backend/app/api/` — HTTP-роутеры;
- `backend/app/models/` — SQLAlchemy-модели;
- `backend/app/services/` — бизнес-логика;
- `backend/app/bootstrap/` — стартовые задачи, создание совместимой схемы, seed суперпользователя;
- `backend/app/core/` — конфиг, БД, permissions, время, request context.

Основные роутеры подключены в `backend/app/main.py`:

- `/auth`
- `/orders`
- `/cash`
- `/documents`
- `/price-list`
- `/settings`
- `/analytics`
- `/employees`
- `/warehouse`
- `/form-history`
- `/audit`
- `/health`

## Frontend

Frontend — статические HTML/CSS/JS файлы без сборщика.

Основные страницы:

- `login.html` — вход;
- `index.html` — оформление документов;
- `cash-shifts.html` — касса документов;
- `plate-transfer.html` — деньги за номера;
- `plate-operator.html` — изготовление номеров;
- `plate-cash.html` — касса номеров;
- `warehouse.html` — склад;
- `analytics-docs.html` — аналитика документов;
- `analytics-plates.html` — аналитика номеров;
- `plate-report.html` — отчет по номерам;
- `admin.html`, `users.html`, `account.html` — управление.

Общий стиль лежит в `frontend/styles.css`. Тема светлая/темная задается CSS-переменными, а переключение хранится на клиенте.

## Локальный запуск

Требования:

- Python 3.11+
- PostgreSQL для ручного локального запуска;
- Node.js для проверки JS-синтаксиса;
- nginx нужен только на сервере.

Подготовить env:

```bash
cd backend
cp .env.example .env
```

Минимальный локальный пример:

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w
JWT_SECRET=
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=admin1234
SUPERUSER_NAME=Администратор
```

Запустить backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Проверить:

```bash
curl http://127.0.0.1:8000/health
```

Запустить frontend:

```bash
cd frontend
python3 -m http.server 8080
```

Открыть `http://127.0.0.1:8080/login.html`.

## Переменные окружения

Production-значения хранятся только на сервере в `backend/.env`.

Обязательные значения:

```env
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://eye_user:your_password@localhost:5432/eye_w
JWT_SECRET=long_random_secret
CORS_ORIGINS=https://your-domain.example
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=strong_password
SUPERUSER_NAME=Администратор
```

В git нельзя коммитить реальные `.env`, дампы БД, логи, backup-файлы, токены и пароли.

## База данных и миграции

Source of truth для схемы — Alembic.

Файлы:

- `alembic.ini`;
- `alembic/env.py`;
- `alembic/versions/`;
- `backend/app/bootstrap/schema.py` — переходный слой совместимости для уже развернутых установок.

Команды:

```bash
alembic current
alembic upgrade head
alembic revision -m "short description"
```

Правила:

- новая схема добавляется новой Alembic-ревизией;
- автогенерацию можно использовать только как черновик;
- исторические ревизии не должны зависеть от будущих изменений моделей;
- `create_schema` и `ensure_schema_compatibility` не заменяют миграции.

## Серверный деплой

Ожидаемый серверный контур:

- код проекта в `/opt/eye_w`;
- PostgreSQL;
- nginx;
- `backend/.venv`;
- systemd-сервис `eye_w`;
- production env в `/opt/eye_w/backend/.env`.

Базовый деплой:

```bash
cd /opt/eye_w
bash deploy/setup_server.sh
bash deploy/check_stack.sh
```

`deploy/setup_server.sh`:

- создает/обновляет недостающие переменные в `backend/.env`;
- обновляет nginx-конфиг;
- устанавливает backend-зависимости, если есть `backend/.venv`;
- запускает совместимое создание схемы;
- применяет Alembic-миграции, если установлен Alembic;
- перезапускает `eye_w`;
- проверяет `/health`.

Сервис создается как `/etc/systemd/system/eye_w.service` и должен работать не от `root`, а от системного пользователя `eye_w`.

## nginx

Рабочий конфиг: `deploy/nginx-eye_w.conf`.

Подключение вручную:

```bash
cp /opt/eye_w/deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
ln -sf /etc/nginx/sites-available/eye_w /etc/nginx/sites-enabled/eye_w
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

nginx должен отдавать статический frontend и проксировать API к backend на `127.0.0.1:8000`.

Для production нужен HTTPS. После выпуска сертификата обновить `CORS_ORIGINS` на HTTPS-домен и проверить вход через nginx.

## Бэкап и восстановление

Сделать backup:

```bash
cd /opt/eye_w
bash deploy/backup_db.sh
```

По умолчанию dump сохраняется в `/var/backups/eye_w`. Директорию можно переопределить:

```bash
BACKUP_DIR=/opt/eye_w_db_backups bash deploy/backup_db.sh
```

Скрипт создает `custom` dump PostgreSQL вида `eye_w_YYYYMMDD_HHMMSS.dump`.

Восстановление в пустую БД:

```bash
dropdb eye_w
createdb -O eye_user eye_w
pg_restore --clean --if-exists --no-owner \
  -d postgresql://eye_user:your_password@localhost:5432/eye_w \
  /var/backups/eye_w/eye_w_YYYYMMDD_HHMMSS.dump
systemctl restart eye_w
bash /opt/eye_w/deploy/check_stack.sh
```

Перед любыми операциями с production-данными backup обязателен.

## Проверки

Локальная релизная проверка:

```bash
bash scripts/release_smoke.sh
```

Скрипт выполняет:

- `compileall` для backend, tests и alembic;
- ключевые pytest-сценарии;
- полный backend test suite;
- `node --check` для frontend JS;
- проверку ссылок на локальные JS/CSS-ассеты в HTML.

Backend-тесты изолированы: каждый тест использует временную SQLite-БД, создает схему и seed'ит тестового администратора. Реальный Postgres и production `.env` не нужны.

Серверная проверка после деплоя:

```bash
cd /opt/eye_w
bash deploy/check_stack.sh
```

Скрипт проверяет:

- `/health` напрямую и через nginx;
- что `eye_w` не работает от `root`;
- логин через `/auth/login`;
- `/auth/me` напрямую и через nginx;
- `/analytics/dashboard` через nginx;
- выдачу ключевых статических страниц.

Скрипт создает временного smoke-пользователя `__smoke_check__` и при выходе деактивирует его. Он не должен создавать заказы, кассовые строки или складские движения.

## Ручной smoke после изменений

Минимум перед релизом:

1. Войти администратором.
2. Создать заказ без номеров и принять оплату.
3. Проверить строку в кассе документов.
4. Создать заказ с номерами.
5. Проверить заказ на странице изготовления номеров.
6. Перенести деньги за номера в промежуточную кассу.
7. Передать деньги в кассу номеров и проверить сумму и количество.
8. Провести заказ по статусам до готовности.
9. Проверить склад.
10. Проверить аналитику документов и номеров.

## Роли и доступы

RBAC описан в `backend/app/core/permissions.py`.

Проверять вручную:

- `ROLE_ADMIN` видит аналитику, админку, аккаунты и настройки;
- `ROLE_MANAGER` видит оба павильона, кассы и склад, но не аналитику и аккаунты;
- `ROLE_OPERATOR` видит форму, кассу документов и деньги за номера;
- `ROLE_PLATE_OPERATOR` видит изготовление номеров, кассу номеров и склад.

Запрещенный раздел должен блокироваться backend'ом, а не только скрываться в меню.

## Диагностика production

```bash
systemctl status eye_w
journalctl -u eye_w --no-pager -n 100
nginx -t
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
```

Если backend отвечает напрямую, но не через nginx, смотреть nginx-конфиг и proxy routes. Если не работает login, проверять `SUPERUSER_*`, хеш пароля и `deploy/check_stack.sh`.

## Безопасность

Перед показом, передачей или релизом:

```bash
git status --short
git ls-files | grep -E '(^|/)\\.env$|\\.dump$|\\.log$|backups/'
rg -n 'JWT_SECRET|SUPERUSER_PASSWORD|DATABASE_URL|password|secret|token' . \
  -g '!backend/.venv/**' \
  -g '!*.docx' \
  -g '!docs/TECHNICAL.md'
bash scripts/release_smoke.sh
```

Ожидаемо:

- нет tracked production `.env`;
- нет дампов, логов и backup-файлов в git;
- нет реальных паролей или токенов;
- release smoke проходит.

## Правило документации

Новые заметки не добавляются отдельными файлами, если они описывают текущий проект. Обновлять нужно один из двух документов:

- бизнес и сценарии — `docs/PROJECT.md`;
- техника, деплой и обслуживание — `docs/TECHNICAL.md`.
