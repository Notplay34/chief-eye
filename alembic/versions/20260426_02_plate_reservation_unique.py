"""make plate reservations unique per order"""

from alembic import op


revision = "20260426_02"
down_revision = "20260426_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM plate_reservations newer
        USING plate_reservations older
        WHERE newer.order_id = older.order_id
          AND newer.id > older.id;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_plate_reservations_order_id_unique
        ON plate_reservations (order_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_plate_reservations_order_id_unique")
