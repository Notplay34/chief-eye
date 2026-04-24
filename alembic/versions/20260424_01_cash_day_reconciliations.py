"""add cash day reconciliations"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_01"
down_revision = "20260423_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_day_reconciliations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pavilion", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("program_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("difference", sa.Numeric(12, 2), nullable=False),
        sa.Column("reconciled_by_id", sa.Integer(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["reconciled_by_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pavilion", "business_date", name="uq_cash_day_reconciliations_pavilion_date"),
    )


def downgrade() -> None:
    op.drop_table("cash_day_reconciliations")
