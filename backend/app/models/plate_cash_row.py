"""Касса номеров: строка — фамилия и сумма (сумма может быть отрицательной, например изъятие из кассы)."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlateCashRow(Base):
    __tablename__ = "plate_cash_rows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
