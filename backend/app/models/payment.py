import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Enum, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PaymentType(str, enum.Enum):
    STATE_DUTY = "STATE_DUTY"
    INCOME_PAVILION1 = "INCOME_PAVILION1"
    INCOME_PAVILION2 = "INCOME_PAVILION2"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[PaymentType] = mapped_column(Enum(PaymentType), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    shift_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cash_shifts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payments")
    employee = relationship("Employee", back_populates="payments")
    shift = relationship("CashShift", backref="payments")
