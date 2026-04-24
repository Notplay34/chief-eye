# Миграции БД

Source of truth для схемы БД теперь `Alembic`.

## Что используется сейчас

- Конфиг: [alembic.ini](/Users/NotPlay/Documents/dev/pavilion/alembic.ini)
- Среда миграций: [alembic/env.py](/Users/NotPlay/Documents/dev/pavilion/alembic/env.py)
- Ревизии: [alembic/versions](/Users/NotPlay/Documents/dev/pavilion/alembic/versions)
- Baseline-ревизия: [alembic/versions/20260423_01_baseline_internal_safe.py](/Users/NotPlay/Documents/dev/pavilion/alembic/versions/20260423_01_baseline_internal_safe.py)
- Текущая ревизия кассовых дней: [alembic/versions/20260424_01_cash_day_reconciliations.py](/Users/NotPlay/Documents/dev/pavilion/alembic/versions/20260424_01_cash_day_reconciliations.py)

## Текущий контракт

1. Новые изменения схемы добавляются только через новую ревизию Alembic.
2. `backend/app/bootstrap/schema.py` остаётся как переходный слой совместимости для уже развернутых инсталляций.
3. Если новая таблица критична для старых установок, её можно продублировать в `ensure_schema_compatibility(...)`, но Alembic-ревизия всё равно обязательна.

## Базовые команды

Проверить текущую ревизию:

```bash
cd /Users/NotPlay/Documents/dev/pavilion
alembic current
```

Применить все миграции:

```bash
cd /Users/NotPlay/Documents/dev/pavilion
alembic upgrade head
```

Создать новую ревизию:

```bash
cd /Users/NotPlay/Documents/dev/pavilion
alembic revision -m "short description"
```

Автогенерацию использовать только как черновик, потом вручную проверять SQL и совместимость.

## Как выкатывать изменения

1. Подтянуть код.
2. Активировать backend-окружение.
3. Выполнить `alembic upgrade head`.
4. Перезапустить сервис приложения.
5. Прогнать [docs/SMOKE_TEST.md](/Users/NotPlay/Documents/dev/pavilion/docs/SMOKE_TEST.md) и `bash deploy/check_stack.sh`.

`deploy/setup_server.sh` выполняет `alembic upgrade head` автоматически, если Alembic установлен в `backend/.venv`.

## Переходный период

На старых установках приложение всё ещё может стартовать через `create_all + ensure_schema_compatibility`, но это fallback, а не основной путь. Для нового деплоя и всех следующих изменений ориентир только один: Alembic-ревизии в репозитории.
