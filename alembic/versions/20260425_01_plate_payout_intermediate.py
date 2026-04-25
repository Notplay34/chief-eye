"""add intermediate plate payout fields"""

from alembic import op


revision = "20260425_01"
down_revision = "20260424_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='plate_payouts'
                  AND column_name='quantity'
            ) THEN
                ALTER TABLE plate_payouts ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='plate_payouts'
                  AND column_name='transferred_at'
            ) THEN
                ALTER TABLE plate_payouts ADD COLUMN transferred_at TIMESTAMP WITHOUT TIME ZONE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='plate_payouts'
                  AND column_name='transferred_by_id'
            ) THEN
                ALTER TABLE plate_payouts ADD COLUMN transferred_by_id INTEGER REFERENCES employees(id);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='plate_payouts'
                  AND column_name='transfer_batch'
            ) THEN
                ALTER TABLE plate_payouts ADD COLUMN transfer_batch VARCHAR(64);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE plate_payouts DROP COLUMN IF EXISTS transfer_batch")
    op.execute("ALTER TABLE plate_payouts DROP COLUMN IF EXISTS transferred_by_id")
    op.execute("ALTER TABLE plate_payouts DROP COLUMN IF EXISTS transferred_at")
    op.execute("ALTER TABLE plate_payouts DROP COLUMN IF EXISTS quantity")
