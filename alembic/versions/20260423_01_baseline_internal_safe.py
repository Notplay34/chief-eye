"""baseline internal safe schema"""

from alembic import op

from app import models  # noqa: F401 - register SQLAlchemy models on metadata
from app.core.database import Base


revision = "20260423_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
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
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
