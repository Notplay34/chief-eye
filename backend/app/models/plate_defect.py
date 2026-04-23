"""Учёт браков: каждая запись — списание 1 шт с датой (для счётчика за месяц)."""
from datetime import datetime
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlateDefect(Base):
    """Запись о списании брака (1 шт, дата для отчёта за месяц)."""
    __tablename__ = "plate_defects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
