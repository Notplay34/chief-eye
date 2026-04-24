"""add cash day reconciliations"""

from alembic import op


revision = "20260424_01"
down_revision = "20260423_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cash_day_reconciliations (
            id SERIAL PRIMARY KEY,
            pavilion INTEGER NOT NULL,
            business_date DATE NOT NULL,
            program_total NUMERIC(12,2) NOT NULL,
            actual_balance NUMERIC(12,2) NOT NULL,
            difference NUMERIC(12,2) NOT NULL,
            reconciled_by_id INTEGER NOT NULL REFERENCES employees(id),
            reconciled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            note VARCHAR(500),
            CONSTRAINT uq_cash_day_reconciliations_pavilion_date UNIQUE (pavilion, business_date)
        );
    """)


def downgrade() -> None:
    op.drop_table("cash_day_reconciliations")
