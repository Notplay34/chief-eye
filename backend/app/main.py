from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.core.database import engine, Base, async_session_maker
from app.core.logging_config import setup_logging, get_logger
from app.models import DocumentPrice, Employee
from app.models.employee import EmployeeRole
from app.data.price_list import PRICE_LIST as DEFAULT_PRICE_LIST
from app.api.orders import router as orders_router
from app.api.employees import router as employees_router
from app.api.documents import router as documents_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.cash import router as cash_router
from app.api.price_list import router as price_list_router
from app.api.warehouse import router as warehouse_router
from app.api.form_history import router as form_history_router
from app.services.auth_service import hash_password
from app.config import settings

setup_logging()
logger = get_logger(__name__)


async def ensure_columns_and_enum():
    """Добавить колонки login, password_hash и ROLE_MANAGER в enum для старых БД."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' AND column_name='login') THEN
                    ALTER TABLE employees ADD COLUMN login VARCHAR(64) UNIQUE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' AND column_name='password_hash') THEN
                    ALTER TABLE employees ADD COLUMN password_hash VARCHAR(255);
                END IF;
            END $$;
        """))
        # Колонка public_id в orders (если таблица создавалась старой версией)
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='orders' AND column_name='public_id') THEN
                    ALTER TABLE orders ADD COLUMN public_id VARCHAR(36);
                    UPDATE orders SET public_id = gen_random_uuid()::text WHERE public_id IS NULL;
                    ALTER TABLE orders ALTER COLUMN public_id SET NOT NULL;
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_public_id ON orders (public_id);
                END IF;
            END $$;
        """))
        # Таблица cash_shifts (кассы и смены)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cash_shifts (
                id SERIAL PRIMARY KEY,
                pavilion INTEGER NOT NULL,
                opened_by_id INTEGER NOT NULL REFERENCES employees(id),
                opened_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                closed_at TIMESTAMP WITHOUT TIME ZONE,
                closed_by_id INTEGER REFERENCES employees(id),
                opening_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                closing_balance NUMERIC(12,2),
                status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
            );
        """))
        # Колонка shift_id в payments
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='payments' AND column_name='shift_id') THEN
                    ALTER TABLE payments ADD COLUMN shift_id INTEGER REFERENCES cash_shifts(id);
                END IF;
            END $$;
        """))
        # Таблица cash_rows — таблица кассы (ФИО, заявление, госпошлина, ДКП, страховка, номера, итого)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cash_rows (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                client_name VARCHAR(255) NOT NULL DEFAULT '',
                application NUMERIC(12,2) NOT NULL DEFAULT 0,
                state_duty NUMERIC(12,2) NOT NULL DEFAULT 0,
                dkp NUMERIC(12,2) NOT NULL DEFAULT 0,
                insurance NUMERIC(12,2) NOT NULL DEFAULT 0,
                plates NUMERIC(12,2) NOT NULL DEFAULT 0,
                total NUMERIC(12,2) NOT NULL DEFAULT 0
            );
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='cash_rows' AND column_name='created_at') THEN
                    ALTER TABLE cash_rows ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
                END IF;
            END $$;
        """))
        # Касса номеров: фамилия и сумма (сумма может быть отрицательной)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_cash_rows (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                client_name VARCHAR(255) NOT NULL DEFAULT '',
                amount NUMERIC(12,2) NOT NULL DEFAULT 0
            );
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='created_at') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
                END IF;
            END $$;
        """))
        # Реестр выдач денег за номера (между кассой документов и кассой номеров)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_payouts (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                client_name VARCHAR(255) NOT NULL DEFAULT '',
                amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                paid_at TIMESTAMP WITHOUT TIME ZONE,
                paid_by_id INTEGER REFERENCES employees(id)
            );
        """))
        # Склад заготовок номеров
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_stock (
                id SERIAL PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_reservations (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                quantity INTEGER NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        # Учёт браков (для счётчика за месяц)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_defects (
                id SERIAL PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        # История заполнения формы (при «Деньги получены»)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS form_history (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
                form_data JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
    try:
        async with engine.connect() as conn:
            await conn.execute(text("ALTER TYPE employeerole ADD VALUE 'ROLE_MANAGER'"))
            await conn.commit()
    except Exception as e:
        if "already exists" not in str(e).lower():
            logger.warning("Enum ROLE_MANAGER: %s", e)


async def ensure_superuser():
    """Создать суперпользователя при первом запуске, если такого логина ещё нет. Логин/пароль/имя из .env (SUPERUSER_LOGIN, SUPERUSER_PASSWORD, SUPERUSER_NAME)."""
    login = (settings.superuser_login or "").strip()
    if not login:
        return
    async with async_session_maker() as session:
        r = await session.execute(select(Employee).where(Employee.login == login))
        if r.scalar_one_or_none() is not None:
            return
        password = settings.superuser_password or ""
        name = (settings.superuser_name or login).strip()
        emp = Employee(
            name=name,
            role=EmployeeRole.ROLE_ADMIN,
            login=login,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(emp)
        await session.commit()
        logger.info("Создан суперпользователь: %s", login)


async def seed_document_prices():
    """Заполнить прейскурант из дефолтного списка, если таблица пуста."""
    async with async_session_maker() as session:
        r = await session.execute(select(DocumentPrice).limit(1))
        if r.scalar_one_or_none() is not None:
            return
        for i, item in enumerate(DEFAULT_PRICE_LIST):
            row = DocumentPrice(
                template=item["template"],
                label=item["label"],
                price=item["price"],
                sort_order=i,
            )
            session.add(row)
        await session.commit()
        logger.info("Прейскурант заполнен из дефолтного списка (%s позиций)", len(DEFAULT_PRICE_LIST))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы БД проверены/созданы")
    try:
        await ensure_columns_and_enum()
    except Exception as e:
        logger.warning("Миграция колонок: %s", e)
    try:
        await ensure_superuser()
    except Exception as e:
        logger.warning("Суперпользователь: %s", e)
    try:
        await seed_document_prices()
    except Exception as e:
        logger.warning("Прейскурант: %s", e)
    yield
    await engine.dispose()


app = FastAPI(title="Павильоны МРЭО", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Необработанная ошибка: %s", exc)
    detail = "Внутренняя ошибка сервера"
    err_str = str(exc).lower()
    if "duplicate key" in err_str or "unique constraint" in err_str:
        detail = "Конфликт данных (дубликат). Обновите страницу и повторите."
    elif "foreign key" in err_str or "violates foreign key" in err_str:
        detail = "Ошибка связи с данными (например, сотрудник не найден). Выйдите и войдите снова."
    elif "column" in err_str and "does not exist" in err_str:
        detail = "Устаревшая схема БД. Перезапустите сервис: systemctl restart eye_w"
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )

_cors_origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(orders_router)
app.include_router(cash_router)
app.include_router(documents_router)
app.include_router(price_list_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(warehouse_router)
app.include_router(form_history_router)


@app.get("/health")
def health():
    return {"status": "ok"}
