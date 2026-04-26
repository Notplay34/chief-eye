"""Резерв заготовок под заказ (при переходе в изготовление)."""
from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlateReservation(Base):
    """Резерв заготовок под заказ (order_id → quantity)."""
    __tablename__ = "plate_reservations"
    __table_args__ = (UniqueConstraint("order_id", name="uq_plate_reservations_order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
