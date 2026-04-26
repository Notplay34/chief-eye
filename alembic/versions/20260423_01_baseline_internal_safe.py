"""baseline internal safe schema"""

from alembic import op


revision = "20260423_01"
down_revision = None
branch_labels = None
depends_on = None


BASELINE_SQL = [
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'employeerole') THEN
            CREATE TYPE employeerole AS ENUM ('ROLE_ADMIN', 'ROLE_MANAGER', 'ROLE_OPERATOR', 'ROLE_PLATE_OPERATOR');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderstatus') THEN
            CREATE TYPE orderstatus AS ENUM ('CREATED', 'AWAITING_PAYMENT', 'PAID', 'PLATE_IN_PROGRESS', 'PLATE_READY', 'COMPLETED', 'PROBLEM');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymenttype') THEN
            CREATE TYPE paymenttype AS ENUM ('STATE_DUTY', 'INCOME_PAVILION1', 'INCOME_PAVILION2');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'platestatus') THEN
            CREATE TYPE platestatus AS ENUM ('IN_PROGRESS', 'READY', 'EXTRA_PAID', 'PROBLEM');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shiftstatus') THEN
            CREATE TYPE shiftstatus AS ENUM ('OPEN', 'CLOSED');
        END IF;
    END $$;
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        id SERIAL PRIMARY KEY,
        setting_key VARCHAR(100) NOT NULL UNIQUE,
        setting_value VARCHAR(255) NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_rows (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        client_name VARCHAR(255) NOT NULL,
        application NUMERIC(12, 2) NOT NULL,
        state_duty NUMERIC(12, 2) NOT NULL,
        dkp NUMERIC(12, 2) NOT NULL,
        insurance NUMERIC(12, 2) NOT NULL,
        plates NUMERIC(12, 2) NOT NULL,
        total NUMERIC(12, 2) NOT NULL,
        source_type VARCHAR(64),
        source_date DATE,
        source_batch VARCHAR(64)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS document_prices (
        id SERIAL PRIMARY KEY,
        template VARCHAR(64) NOT NULL UNIQUE,
        label VARCHAR(255) NOT NULL,
        price NUMERIC(12, 2) NOT NULL,
        sort_order INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        role employeerole NOT NULL,
        telegram_id BIGINT,
        login VARCHAR(64) UNIQUE,
        login_normalized VARCHAR(64) UNIQUE,
        password_hash VARCHAR(255),
        is_active BOOLEAN NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_cash_rows (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        client_name VARCHAR(255) NOT NULL,
        quantity INTEGER NOT NULL,
        amount NUMERIC(12, 2) NOT NULL,
        source_type VARCHAR(64),
        source_date DATE,
        source_batch VARCHAR(64)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_defects (
        id SERIAL PRIMARY KEY,
        quantity INTEGER NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_stock (
        id SERIAL PRIMARY KEY,
        quantity INTEGER NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_stock_movements (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        movement_type VARCHAR(32) NOT NULL,
        quantity_delta INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        source_type VARCHAR(64),
        source_id INTEGER,
        note VARCHAR(255)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        actor_employee_id INTEGER REFERENCES employees(id),
        event_type VARCHAR(64) NOT NULL,
        entity_type VARCHAR(64) NOT NULL,
        entity_id INTEGER,
        payload_json JSONB NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_day_reconciliations (
        id SERIAL PRIMARY KEY,
        pavilion INTEGER NOT NULL,
        business_date DATE NOT NULL,
        program_total NUMERIC(12, 2) NOT NULL,
        actual_balance NUMERIC(12, 2) NOT NULL,
        difference NUMERIC(12, 2) NOT NULL,
        reconciled_by_id INTEGER NOT NULL REFERENCES employees(id),
        reconciled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        note VARCHAR(500),
        CONSTRAINT uq_cash_day_reconciliations_pavilion_date UNIQUE (pavilion, business_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_shifts (
        id SERIAL PRIMARY KEY,
        pavilion INTEGER NOT NULL,
        opened_by_id INTEGER NOT NULL REFERENCES employees(id),
        opened_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        closed_at TIMESTAMP WITHOUT TIME ZONE,
        closed_by_id INTEGER REFERENCES employees(id),
        opening_balance NUMERIC(12, 2) NOT NULL,
        closing_balance NUMERIC(12, 2),
        status shiftstatus NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS intermediate_plate_transfers (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        client_name VARCHAR(255) NOT NULL,
        quantity INTEGER NOT NULL,
        amount NUMERIC(12, 2) NOT NULL,
        created_by_id INTEGER REFERENCES employees(id),
        paid_at TIMESTAMP WITHOUT TIME ZONE,
        paid_by_id INTEGER REFERENCES employees(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        public_id VARCHAR(36) NOT NULL UNIQUE,
        status orderstatus NOT NULL,
        total_amount NUMERIC(12, 2) NOT NULL,
        state_duty_amount NUMERIC(12, 2) NOT NULL,
        income_pavilion1 NUMERIC(12, 2) NOT NULL,
        income_pavilion2 NUMERIC(12, 2) NOT NULL,
        need_plate BOOLEAN NOT NULL,
        service_type VARCHAR(64),
        form_data JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        employee_id INTEGER REFERENCES employees(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS form_history (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id),
        form_data JSONB,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        amount NUMERIC(12, 2) NOT NULL,
        type paymenttype NOT NULL,
        employee_id INTEGER REFERENCES employees(id),
        shift_id INTEGER REFERENCES cash_shifts(id),
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_payouts (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        client_name VARCHAR(255) NOT NULL,
        quantity INTEGER NOT NULL,
        amount NUMERIC(12, 2) NOT NULL,
        transferred_at TIMESTAMP WITHOUT TIME ZONE,
        transferred_by_id INTEGER REFERENCES employees(id),
        transfer_batch VARCHAR(64),
        paid_at TIMESTAMP WITHOUT TIME ZONE,
        paid_by_id INTEGER REFERENCES employees(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plate_reservations (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        quantity INTEGER NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        CONSTRAINT uq_plate_reservations_order_id UNIQUE (order_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS plates (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        plate_type VARCHAR(64),
        status platestatus NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
    );
    """,
]


def upgrade() -> None:
    for statement in BASELINE_SQL:
        op.execute(statement)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_employees_login_normalized
        ON employees (login_normalized)
        WHERE login_normalized IS NOT NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_public_id
        ON orders (public_id);
    """)


def downgrade() -> None:
    for table in (
        "plates",
        "plate_reservations",
        "plate_payouts",
        "payments",
        "form_history",
        "orders",
        "intermediate_plate_transfers",
        "cash_shifts",
        "cash_day_reconciliations",
        "audit_logs",
        "plate_stock_movements",
        "plate_stock",
        "plate_defects",
        "plate_cash_rows",
        "employees",
        "document_prices",
        "cash_rows",
        "app_settings",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for enum_type in ("shiftstatus", "platestatus", "paymenttype", "orderstatus", "employeerole"):
        op.execute(f"DROP TYPE IF EXISTS {enum_type}")
