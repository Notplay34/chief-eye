from decimal import Decimal

from sqlalchemy import String, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentPrice(Base):
    __tablename__ = "document_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
