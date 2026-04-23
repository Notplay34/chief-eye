import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Enum, Boolean, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    PLATE_IN_PROGRESS = "PLATE_IN_PROGRESS"
    PLATE_READY = "PLATE_READY"
    COMPLETED = "COMPLETED"
    PROBLEM = "PROBLEM"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4())
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.CREATED, nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    state_duty_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    income_pavilion1: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    income_pavilion2: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    need_plate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    service_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    form_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)

    employee = relationship("Employee", back_populates="orders")
    payments = relationship("Payment", back_populates="order")
    plates = relationship("Plate", back_populates="order")
