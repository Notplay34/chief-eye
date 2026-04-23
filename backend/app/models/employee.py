import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Enum, Boolean, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmployeeRole(str, enum.Enum):
    ROLE_ADMIN = "ROLE_ADMIN"
    ROLE_MANAGER = "ROLE_MANAGER"
    ROLE_OPERATOR = "ROLE_OPERATOR"
    ROLE_PLATE_OPERATOR = "ROLE_PLATE_OPERATOR"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[EmployeeRole] = mapped_column(Enum(EmployeeRole), nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    login: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="employee")
    payments = relationship("Payment", back_populates="employee")
