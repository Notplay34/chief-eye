"""Склад заготовок номеров: остаток, пополнение, списание при изготовлении."""
from datetime import datetime
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlateStock(Base):
    """Остаток заготовок номеров на складе (одна строка — текущий баланс)."""
    __tablename__ = "plate_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
