"""baseline internal safe schema"""

from alembic import op


revision = "20260423_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            actor_employee_id INTEGER REFERENCES employees(id),
            event_type VARCHAR(64) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            entity_id INTEGER,
            payload_json JSON NOT NULL
        );
    """)
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
    op.drop_index("ix_orders_public_id", table_name="orders")
    op.drop_index("ix_employees_login_normalized", table_name="employees")
    op.drop_table("audit_logs")
