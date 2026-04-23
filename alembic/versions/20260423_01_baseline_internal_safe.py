"""baseline internal safe schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("actor_employee_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employees_login_normalized", "employees", ["login_normalized"], unique=True)
    op.create_index("ix_orders_public_id", "orders", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_orders_public_id", table_name="orders")
    op.drop_index("ix_employees_login_normalized", table_name="employees")
    op.drop_table("audit_logs")
