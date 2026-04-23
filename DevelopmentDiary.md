## DevelopmentDiary

> Исторический дневник разработки.
> Содержит промежуточные идеи и удалённые направления, включая уже убранные эксперименты.

### 2026-02-18 — Старт Django-реализации поверх eye_w

- **Контекст**: существующий backend на FastAPI/SQLAlchemy (`backend/app`), фронтенд-форма `OrderCreate`, генерация документов через `docx_service` и `PLACEHOLDER_TO_FIELD`, расчёт `total_amount` и структура прайс-листа уже работают в продакшене.
- **Цель**: поэтапно внедрить Django ORM и сервисный слой для внутренних операций (документы, платежи, касса, склад), минимизируя риск для текущей системы и сохраняя обратную совместимость.

#### Сделано в итерации 1 (MVP Document/Payment на Django, без Telegram и склада)

- Определены целевые статусы:
  - **FinancialStatus**: `UNPAID`, `PARTIALLY_PAID`, `FULLY_PAID`, `OVERPAID` (вычисляются по сумме платежей и `total_amount`, не редактируются вручную).
  - **OperationalStatus**: `CREATED`, `READY_FOR_PAYMENT`, `IN_PROGRESS`, `SENT_TO_PRODUCTION`, `IN_PRODUCTION`, `PRODUCED`, `COMPLETED`, `CANCELLED`, `PROBLEM` (меняются только через сервисный слой).
- Принято решение:
  - На первом этапе **не трогать существующие таблицы FastAPI** и не ломать API, а добавлять параллельные Django-модели и сервисы, используя ту же PostgreSQL-схему.
  - Использовать текущую форму `OrderCreate` и маппинг `PLACEHOLDER_TO_FIELD` как единственный источник правды для полей документа.
- Спроектированы базовые Django-модели для первой итерации:
  - `Document` — агрегат заказа, хранит `form_data` (JSONB), финансовые поля и разделённые статусы.
  - `DocumentItem` — позиции/документы заказа (по прайс-листу).
  - `Payment` — отдельные частичные платежи с типами (`STATE_DUTY`, `INCOME_PAVILION1`, `INCOME_PAVILION2`).
- Спроектированы сервисы:
  - `DocumentService` — создание документа из `OrderCreate`, пересчёт `total_amount`, управление операционным статусом.
  - `PaymentService` — приём частичных платежей, атомарное пересечение с документом и пересчёт `financial_status` без автоматического распределения сумм по типам.

> Решение: на первом этапе `total_amount` хранится явно и заполняется по данным формы (как в текущем FastAPI). В следующих итерациях `total_amount` и составляющие будут вычисляться из `DocumentItem` (сумма по позициям) и/или конфигурации прайс-листа, чтобы убрать дублирование логики и уменьшить риск расхождений.

#### 2026-02-18 — Этап B: Запуск Django-ядра Document/Payment

- Создан полноценный Django-проект в `django_backend/`:
  - `manage.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`
  - Подключение к той же PostgreSQL (парсинг `DATABASE_URL` из backend)
- Убрана зависимость от FastAPI: `documents/price_list.py` — локальная копия прайс-листа
- Исправлено: `DocumentService.create_document` устанавливает `public_id=uuid.uuid4()`
- Добавлен `django_backend/requirements.txt` (Django, psycopg2-binary)
- Добавлен `django_backend/README.md` — инструкции по установке, миграциям и запуску
- Django-API (`/django/documents/`, `/django/documents/{id}/payments/`, `GET /django/documents/{id}/`) готов к запуску на порту 8001

#### 2026-02-18 — Этап А: Инструкции для стейкхолдера

- Создан **INSTALL.md** — пошаговая установка «с нуля» и обновление (для владельца, без техжаргона).
- Создан **USER_GUIDE.md** — как пользоваться: оператор документов, павильон 2, владелец, роли.
- Обновлён **deploy/setup_server.sh** — при первом запуске автоматически создаётся systemd-сервис `eye_w.service`, если его нет.
- Обновлён **README.md** — ссылки на INSTALL и USER_GUIDE.

#### 2026-02-18 — Удаление Telegram, переход на веб-интерфейс павильона 2

- **Решение**: Telegram полностью убран. Оператор изготовления номеров работает через **рабочую ссылку** (веб-интерфейс).
- **Удалено**:
  - `bot_plate/`, `bot_owner/` — директории ботов;
  - `backend/app/services/telegram_notify.py` — уведомления в Telegram;
  - эндпоинт `GET /auth/check-admin` (проверка по telegram_id);
  - переменная `TELEGRAM_BOT_TOKEN_PLATE` из `.env.example`;
  - зависимость `httpx` из requirements.txt.
- **Изменено**:
  - `POST /orders/{id}/pay` — больше не вызывает уведомление в Telegram;
  - `PATCH /orders/{id}/status` — теперь требует JWT с ролью `ROLE_PLATE_OPERATOR` или `ROLE_ADMIN` (вместо заголовка `X-Telegram-User-Id`);
  - добавлен `RequirePlateAccess` в auth.py.
- **Обновлена документация**: PROJECT_CONTEXT, README, DEPLOYMENT, .cursor/rules.
- **Павильон 2 (оператор изготовления)** будет иметь:
  - рабочую ссылку (URL);
  - склад заготовок;
  - кассу павильона;
  - базу не выданных номеров.

#### План на следующее обновление дневника

- Зафиксировать:
  - фактическое добавление Django-моделей и начальных миграций;
  - первые сервисы (`documents/services.py`) с бизнес-правилами статусов и расчёта `financial_status`;
  - стратегию по дальнейшей интеграции с текущим FastAPI (совместный период работы, переключение фронтенда).

#### Позже: удаление Django-слоя из репозитория

- Папка `django_backend/` удалена из репозитория: не использовалась в текущем деплое (nginx и systemd настроены только на FastAPI). Вся логика остаётся в `backend/app` (FastAPI + SQLAlchemy).
