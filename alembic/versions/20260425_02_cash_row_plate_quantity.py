"""add manual plate quantity to cash rows"""

from alembic import op


revision = "20260425_02"
down_revision = "20260425_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='cash_rows'
                  AND column_name='plate_quantity'
            ) THEN
                ALTER TABLE cash_rows ADD COLUMN plate_quantity INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE cash_rows DROP COLUMN IF EXISTS plate_quantity")
