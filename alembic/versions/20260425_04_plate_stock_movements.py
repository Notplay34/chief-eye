"""add plate stock movement history"""

from alembic import op


revision = "20260425_04"
down_revision = "20260425_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS plate_stock_movements (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
            movement_type VARCHAR(32) NOT NULL,
            quantity_delta INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            source_type VARCHAR(64),
            source_id INTEGER,
            note VARCHAR(255)
        );
    """)


def downgrade() -> None:
    op.drop_table("plate_stock_movements")
