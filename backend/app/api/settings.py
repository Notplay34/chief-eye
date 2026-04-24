from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireAdmin, RequireFormAccess, UserInfo
from app.core.database import get_db
from app.services.errors import ServiceError
from app.services.settings_service import (
    get_state_duty_settings,
    state_duty_settings_to_dict,
    update_state_duty_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class StateDutySettingsUpdate(BaseModel):
    commission: Decimal = Field(..., ge=0)
    special_2025_cash_amount: Decimal = Field(..., ge=2025)


@router.get("/state-duty")
async def read_state_duty_settings(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireFormAccess),
):
    settings = await get_state_duty_settings(db)
    return state_duty_settings_to_dict(settings)


@router.put("/state-duty")
async def save_state_duty_settings(
    body: StateDutySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAdmin),
):
    try:
        settings = await update_state_duty_settings(db, body.commission, body.special_2025_cash_amount)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return state_duty_settings_to_dict(settings)
