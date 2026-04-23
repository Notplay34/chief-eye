import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlateStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    EXTRA_PAID = "EXTRA_PAID"
    PROBLEM = "PROBLEM"


class Plate(Base):
    __tablename__ = "plates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    plate_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[PlateStatus] = mapped_column(
        Enum(PlateStatus), default=PlateStatus.IN_PROGRESS, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    order = relationship("Order", back_populates="plates")
