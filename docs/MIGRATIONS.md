# Версионирование изменений схемы БД

Все изменения схемы базы данных фиксируются здесь. При добавлении новых таблиц или колонок добавляйте новый пункт с датой и описанием. В будущем можно перейти на Alembic и генерировать миграции автоматически.

---

## Уже выполненные шаги (в порядке применения)

### Старт (create_all)

- Создание таблиц по моделям SQLAlchemy: `employees`, `orders`, `payments`, `document_prices`, `plates` и др. (см. `app.models`). Выполняется при каждом старте приложения: `Base.metadata.create_all`.

### ensure_columns_and_enum (при старте)

1. **employees:** колонки `login` (VARCHAR 64 UNIQUE), `password_hash` (VARCHAR 255) — если отсутствуют.
2. **orders:** колонка `public_id` (VARCHAR 36 NOT NULL UNIQUE), заполнение uuid при отсутствии.
3. **cash_shifts:** создание таблицы (id, pavilion, opened_by_id, opened_at, closed_at, closed_by_id, opening_balance, closing_balance, status).
4. **payments:** колонка `shift_id` (FK на cash_shifts) — если отсутствует.
5. **cash_rows:** создание таблицы (id, created_at, client_name, application, state_duty, dkp, insurance, plates, total); при необходимости добавление created_at.
6. **plate_cash_rows:** создание таблицы (id, created_at, client_name, amount); при необходимости добавление created_at.
7. **plate_stock:** создание таблицы (id, quantity, updated_at).
8. **plate_reservations:** создание таблицы (id, order_id, quantity, created_at).
9. **plate_defects:** создание таблицы (id, quantity, created_at).
10. **form_history:** создание таблицы (id, order_id, form_data, created_at).
11. **Enum employeerole:** добавление значения `ROLE_MANAGER` — если ещё нет.

### Последовательность при деплое

На чистой БД сначала выполняется `create_all`, затем при первом запросе (lifespan) — все шаги `ensure_columns_and_enum`. Новые инсталляции не требуют ручного запуска миграций.

---

## Правила для новых изменений схемы

1. Добавьте описание в этот файл (дата, что сделано, в каком файле/функции).
2. Реализуйте шаг идемпотентно (IF NOT EXISTS / проверка наличия колонки), чтобы повторный запуск не падал.
3. При переименовании моделей или таблиц учитывайте, что в `main.py` есть и create_all, и отдельные CREATE TABLE — при смене имени модели обновите оба места или перейдите на единый источник истины (только модели + миграции).

---

## Пример записи для будущей миграции

```markdown
### 2026-03-XX: таблица X

- Файл: `app/main.py`, функция ensure_columns_and_enum (или новый скрипт deploy/migrate_XX.sql).
- Описание: CREATE TABLE x (id SERIAL PRIMARY KEY, ...).
- Идемпотентность: CREATE TABLE IF NOT EXISTS x ...
```
