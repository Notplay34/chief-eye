"""Schema compatibility helpers executed during application startup."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def ensure_schema_compatibility(engine: AsyncEngine) -> None:
    """Apply idempotent schema compatibility steps for existing databases."""
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
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' AND column_name='login_normalized') THEN
                    ALTER TABLE employees ADD COLUMN login_normalized VARCHAR(64);
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            UPDATE employees
            SET login_normalized = NULLIF(lower(btrim(login)), '')
            WHERE login IS NOT NULL
              AND (
                login_normalized IS NULL
                OR login_normalized <> NULLIF(lower(btrim(login)), '')
              );
        """))
        await conn.execute(text("""
            DO $$
            DECLARE
                duplicate_logins TEXT;
            BEGIN
                SELECT string_agg(login_normalized, ', ')
                INTO duplicate_logins
                FROM (
                    SELECT login_normalized
                    FROM employees
                    WHERE login_normalized IS NOT NULL
                    GROUP BY login_normalized
                    HAVING count(*) > 1
                ) d;

                IF duplicate_logins IS NOT NULL THEN
                    RAISE EXCEPTION 'Найдены конфликтующие логины после нормализации: %', duplicate_logins;
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_employees_login_normalized
            ON employees (login_normalized)
            WHERE login_normalized IS NOT NULL;
        """))
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
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='payments' AND column_name='shift_id') THEN
                    ALTER TABLE payments ADD COLUMN shift_id INTEGER REFERENCES cash_shifts(id);
                END IF;
            END $$;
        """))
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
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='cash_rows' AND column_name='source_type') THEN
                    ALTER TABLE cash_rows ADD COLUMN source_type VARCHAR(64);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='cash_rows' AND column_name='source_date') THEN
                    ALTER TABLE cash_rows ADD COLUMN source_date DATE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='cash_rows' AND column_name='source_batch') THEN
                    ALTER TABLE cash_rows ADD COLUMN source_batch VARCHAR(64);
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id SERIAL PRIMARY KEY,
                setting_key VARCHAR(100) NOT NULL UNIQUE,
                setting_value VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_cash_rows (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                client_name VARCHAR(255) NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 0,
                amount NUMERIC(12,2) NOT NULL DEFAULT 0
            );
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='created_at') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='quantity') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='source_type') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN source_type VARCHAR(64);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='source_date') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN source_date DATE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_cash_rows' AND column_name='source_batch') THEN
                    ALTER TABLE plate_cash_rows ADD COLUMN source_batch VARCHAR(64);
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='cash_rows' AND column_name='plate_quantity') THEN
                    ALTER TABLE cash_rows DROP COLUMN plate_quantity;
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_payouts (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                client_name VARCHAR(255) NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                transferred_at TIMESTAMP WITHOUT TIME ZONE,
                transferred_by_id INTEGER REFERENCES employees(id),
                transfer_batch VARCHAR(64),
                paid_at TIMESTAMP WITHOUT TIME ZONE,
                paid_by_id INTEGER REFERENCES employees(id)
            );
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_payouts' AND column_name='quantity') THEN
                    ALTER TABLE plate_payouts ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_payouts' AND column_name='transferred_at') THEN
                    ALTER TABLE plate_payouts ADD COLUMN transferred_at TIMESTAMP WITHOUT TIME ZONE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_payouts' AND column_name='transferred_by_id') THEN
                    ALTER TABLE plate_payouts ADD COLUMN transferred_by_id INTEGER REFERENCES employees(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plate_payouts' AND column_name='transfer_batch') THEN
                    ALTER TABLE plate_payouts ADD COLUMN transfer_batch VARCHAR(64);
                END IF;
            END $$;
        """))
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
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plate_defects (
                id SERIAL PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS form_history (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
                form_data JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                actor_employee_id INTEGER REFERENCES employees(id),
                event_type VARCHAR(64) NOT NULL,
                entity_type VARCHAR(64) NOT NULL,
                entity_id INTEGER,
                payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cash_day_reconciliations (
                id SERIAL PRIMARY KEY,
                pavilion INTEGER NOT NULL,
                business_date DATE NOT NULL,
                program_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                actual_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                difference NUMERIC(12,2) NOT NULL DEFAULT 0,
                reconciled_by_id INTEGER NOT NULL REFERENCES employees(id),
                reconciled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                note VARCHAR(500),
                CONSTRAINT uq_cash_day_reconciliations_pavilion_date UNIQUE (pavilion, business_date)
            );
        """))

    try:
        async with engine.connect() as conn:
            await conn.execute(text("ALTER TYPE employeerole ADD VALUE 'ROLE_MANAGER'"))
            await conn.commit()
    except Exception as exc:
        if "already exists" not in str(exc).lower():
            logger.warning("Enum ROLE_MANAGER: %s", exc)
