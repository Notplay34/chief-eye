"""Строка кассы: ФИО и суммы по графам (заявление, госпошлина, ДКП, страховка, номера, итого)."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CashRow(Base):
    """Одна строка в таблице кассы — редактируемые ячейки."""
    __tablename__ = "cash_rows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)  # Фамилия и инициалы
    application: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)   # Заявление
    state_duty: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)    # Госпошлина
    dkp: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)           # ДКП
    insurance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)     # Страховка
    plates: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)       # Номера
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)        # Итого
