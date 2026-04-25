# Павильоны МРЭО

Внутренняя система для двух павильонов автоуслуг возле МРЭО:

- павильон 1: оформление документов, приём оплаты, печать `.docx`;
- павильон 2: номера, доплаты, склад заготовок, статусы изготовления;
- директор: аналитика, админка, управление аккаунтами.

Проект построен как один рабочий контур: `FastAPI + PostgreSQL + статический frontend`.

## Актуальные документы

Если нужно быстро понять проект, достаточно этих файлов:

1. `README.md` — общий обзор.
2. `PROJECT_CONTEXT.md` — бизнес-логика и текущая модель ролей.
3. `INSTALL.md` — локальный запуск и первый старт.
4. `USER_GUIDE.md` — пользовательские сценарии.
5. `DEPLOYMENT.md` — серверный деплой.
6. `docs/SMOKE_TEST.md` — финальная проверка после изменений или выката.

Карта репозитория: [docs/REPOSITORY_STATE.md](/Users/NotPlay/Documents/dev/pavilion/docs/REPOSITORY_STATE.md)

## Что уже реализовано

- оформление заказа из единой формы;
- приём оплаты и запись платежей;
- печать документов из шаблонов `templates/*.docx`;
- касса и смены по павильонам;
- список заказов на номера и workflow статусов;
- склад заготовок, резервирование, списание, брак;
- касса документов, промежуточная касса денег за номера и касса номеров;
- аналитика по доходу, обороту, сотрудникам, статусам, месяцам и кварталам;
- управление сотрудниками и роли доступа;
- изолированный backend test suite.

## Стек

- Backend: `FastAPI`, `SQLAlchemy`, `PostgreSQL`
- Frontend: статические `HTML/CSS/JS`
- Deploy: `nginx + systemd`

## Структура

- `backend/` — API, модели, сервисы, тесты
- `frontend/` — рабочие страницы и JS-логика
- `templates/` — шаблоны документов
- `deploy/` — nginx, серверные скрипты, smoke-check
- `docs/` — рабочая документация по состоянию проекта

## Основные эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| `GET` | `/health` | Проверка живости backend |
| `POST` | `/auth/login` | Вход |
| `GET` | `/auth/me` | Текущий пользователь, павильоны и меню |
| `POST` | `/orders` | Создать заказ |
| `POST` | `/orders/{id}/pay` | Принять оплату |
| `POST` | `/orders/{id}/pay-extra` | Доплата за номера |
| `PATCH` | `/orders/{id}/status` | Смена статуса заказа |
| `GET` | `/orders/plate-list` | Рабочий список заказов павильона 2 |
| `GET` | `/cash/shifts/current` | Текущая смена по павильону |
| `GET` | `/cash/plate-payouts` | Деньги за номера к переносу из кассы документов |
| `GET` | `/cash/plate-transfers` | Промежуточная касса денег за номера |
| `GET` | `/warehouse/plate-stock` | Остаток и резервы склада |
| `GET` | `/analytics/dashboard` | Основной управленческий дашборд |
| `GET` | `/employees` | Список сотрудников |

## Локальный запуск

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Документация API: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
python3 -m http.server 8080
```

Открыть: `http://localhost:8080/login.html`

## Тестирование

Backend-тесты полностью изолированы: каждый тест поднимает свою временную SQLite-БД, создаёт схему и seed'ит тестового админа. Внешний Postgres и реальный `.env` для тестов не нужны.

Основные команды:

```bash
python3 -m pytest backend/tests -q
python3 -m compileall backend/app
node --check frontend/*.js frontend/form-page/*.js
bash -n deploy/check_stack.sh
```

Сценарии покрывают:

- логин и `/auth/me`;
- создание заказа и оплату;
- кассу и смены;
- склад;
- аналитику;
- smoke matrix по ролям.
