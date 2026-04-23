"""Касса и смены: открытие/закрытие смены по павильонам."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Enum, Numeric, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CashShift(Base):
    """Смена кассы (павильон 1 или 2)."""
    __tablename__ = "cash_shifts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pavilion: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 или 2
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    closing_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus), default=ShiftStatus.OPEN, nullable=False
    )

    opened_by = relationship("Employee", foreign_keys=[opened_by_id])
    closed_by = relationship("Employee", foreign_keys=[closed_by_id])
