"""move manual plate quantity to plate cash rows"""

from alembic import op


revision = "20260425_03"
down_revision = "20260425_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='cash_rows'
                  AND column_name='plate_quantity'
            ) THEN
                ALTER TABLE cash_rows DROP COLUMN plate_quantity;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='plate_cash_rows'
                  AND column_name='quantity'
            ) THEN
                ALTER TABLE plate_cash_rows ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE plate_cash_rows DROP COLUMN IF EXISTS quantity")
    op.execute("ALTER TABLE cash_rows ADD COLUMN IF NOT EXISTS plate_quantity INTEGER NOT NULL DEFAULT 0")
