from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    setting_value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
