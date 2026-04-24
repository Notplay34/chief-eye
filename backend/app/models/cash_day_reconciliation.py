"""Daily cash reconciliation for the paper-table cash workflow."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CashDayReconciliation(Base):
    __tablename__ = "cash_day_reconciliations"
    __table_args__ = (
        UniqueConstraint("pavilion", "business_date", name="uq_cash_day_reconciliations_pavilion_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pavilion: Mapped[int] = mapped_column(Integer, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    program_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    actual_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reconciled_by_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    reconciled_by = relationship("Employee")
