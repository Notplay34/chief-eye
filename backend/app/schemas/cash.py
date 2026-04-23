"""Схемы для касс и смен."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ShiftOpen(BaseModel):
    """Открыть смену."""
    pavilion: int = Field(..., ge=1, le=2, description="1 — павильон документов, 2 — павильон номеров")
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0)


class ShiftClose(BaseModel):
    """Закрыть смену."""
    closing_balance: Decimal = Field(..., ge=0)


class ShiftResponse(BaseModel):
    id: int
    pavilion: int
    opened_by_id: int
    opened_at: str
    closed_at: Optional[str] = None
    closed_by_id: Optional[int] = None
    opening_balance: Decimal
    closing_balance: Optional[Decimal] = None
    status: str

    class Config:
        from_attributes = True


class ShiftCurrentResponse(BaseModel):
    """Текущая открытая смена + сумма по ней."""
    shift: ShiftResponse
    total_in_shift: Decimal
    """Сумма всех платежей за смену."""


# Таблица кассы: строки с редактируемыми ячейками
class CashRowCreate(BaseModel):
    client_name: str = ""
    application: Decimal = Decimal("0")
    state_duty: Decimal = Decimal("0")
    dkp: Decimal = Decimal("0")
    insurance: Decimal = Decimal("0")
    plates: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class CashRowUpdate(BaseModel):
    client_name: Optional[str] = None
    application: Optional[Decimal] = None
    state_duty: Optional[Decimal] = None
    dkp: Optional[Decimal] = None
    insurance: Optional[Decimal] = None
    plates: Optional[Decimal] = None
    total: Optional[Decimal] = None


class CashRowResponse(BaseModel):
    id: int
    client_name: str
    application: Decimal
    state_duty: Decimal
    dkp: Decimal
    insurance: Decimal
    plates: Decimal
    total: Decimal

    class Config:
        from_attributes = True
