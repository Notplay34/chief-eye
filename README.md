# Павильоны МРЭО — система учёта и контроля

**Версия 1.0** — система управления двумя павильонами автоуслуг: оформление документов, изготовление номеров, учёт платежей и внутренняя операционная работа.

**Быстрый старт:**
- **Установка:** см. **INSTALL.md** — пошаговая инструкция для владельца.
- **Использование:** см. **USER_GUIDE.md** — как работать операторам и владельцу.

**Готово к запуску:** форма документов, изготовление номеров (павильон 2), касса, склад, управление аккаунтами, печать документов.  
**Важно:** раздел аналитики присутствует в интерфейсе, но в текущем состоянии отключён как недоведённый.  
Навигация по актуальным и историческим документам: см. [docs/REPOSITORY_STATE.md](/Users/NotPlay/Documents/dev/pavilion/docs/REPOSITORY_STATE.md).

## Основные документы

Если нужно быстро понять проект без лишней археологии, достаточно этих файлов:

1. `README.md` — что это за проект и как он устроен в целом.
2. `PROJECT_CONTEXT.md` — бизнес-логика и целевая модель системы.
3. `INSTALL.md` — локальная установка и первый запуск.
4. `USER_GUIDE.md` — как системой пользуются сотрудники.

Отдельно для сервера:

- `DEPLOYMENT.md` — продакшн-развёртывание.

Исторические документы и старые планы вынесены в [docs/ARCHIVE.md](/Users/NotPlay/Documents/dev/pavilion/docs/ARCHIVE.md).

---

## Требования

- Python 3.11+
- PostgreSQL
- (Опционально) Node или простой HTTP-сервер для frontend

---

## Backend (FastAPI)

1. Создать виртуальное окружение и установить зависимости:

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. Настроить БД: скопировать `backend/.env.example` в `backend/.env` и задать `DATABASE_URL`:

   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/eye_w
   ```

3. Запуск:

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Документация API: http://localhost:8000/docs

---

## Frontend (веб-форма операторов)

Статические файлы в папке **frontend/** (HTML, CSS, JS). Подключение к API по умолчанию: `http://localhost:8000`.

1. Открыть в браузере файл `frontend/index.html`  
   **или**
2. Запустить любой HTTP-сервер из папки `frontend`, например:

   ```bash
   cd frontend
   python -m http.server 8080
   ```
   Затем открыть http://localhost:8080

---

## Шаблоны документов

Папка **templates/** в корне проекта — шаблоны docx для генерации документов (DKP, МРЭО, заявления и т.д.). Backend подставляет данные заказа в плейсхолдеры `{{ ... }}`.

---

## Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | /health | Проверка работы сервера |
| POST | /orders | Создание заказа |
| POST | /orders/{id}/pay | Принять оплату по заказу |
| GET | /orders | Список заказов |
| GET | /orders/{id} | Заказ по id |
| GET | /orders/{id}/documents/{template} | Скачать сгенерированный docx |
| GET | /employees | Список сотрудников |
| POST | /employees | Создание сотрудника |
| PATCH | /employees/{id} | Обновление сотрудника (имя, роль, is_active) |
| GET | /analytics/today | Сводка за день |
| GET | /analytics/month | Сводка за месяц |
| GET | /analytics/employees | Учёт по сотрудникам |

---

## Павильон 2 — изготовление номеров

Оператор павильона 2 работает через **веб-интерфейс** (plate-operator.html) — логин/пароль, меню «Изготовление номеров». Список заказов с номерами, смена статусов, приём доплат. См. USER_GUIDE.md, раздел «Павильон 2».

---

## Как тестировать

1. **База данных.** Должен быть запущен PostgreSQL с БД `eye_w`.
   - Локально: создать БД и пользователя, в `backend/.env` указать `DATABASE_URL`.
   - Через Docker (если установлен): в корне проекта выполнить `docker compose up -d` — поднимется PostgreSQL (порт 5432, пользователь `eye_user`, пароль `eye_pass`, БД `eye_w`). В `backend/.env` задать:
     ```
     DATABASE_URL=postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w
     ```

2. **Backend:** из корня проекта:
   ```bash
   .venv\Scripts\activate
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Проверка: http://localhost:8000/docs и http://localhost:8000/health

3. **Frontend:** в другом терминале:
   ```bash
   cd frontend
   python -m http.server 8080
   ```
   Открыть http://localhost:8080 — форма оператора. Создать через API или форму заказ, принять оплату, проверить аналитику и скачивание документов.

4. **Сотрудники:** через Swagger (POST /employees) создать сотрудника; PATCH /employees/{id} — обновить (имя, роль, is_active).

---

## Дальнейшая разработка

- История и старые планы сохранены, но часть из них уже устарела.
- Для понимания, какие документы актуальны, а какие исторические, см. `docs/REPOSITORY_STATE.md`.
