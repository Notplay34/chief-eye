"""add manual intermediate plate transfer rows"""

from alembic import op


revision = "20260426_01"
down_revision = "20260425_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS intermediate_plate_transfers (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
            client_name VARCHAR(255) NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL DEFAULT 0,
            amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            created_by_id INTEGER REFERENCES employees(id),
            paid_at TIMESTAMP WITHOUT TIME ZONE,
            paid_by_id INTEGER REFERENCES employees(id)
        );
    """)


def downgrade() -> None:
    op.drop_table("intermediate_plate_transfers")
