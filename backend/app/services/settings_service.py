from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting
from app.services.errors import ServiceError

STATE_DUTY_COMMISSION_KEY = "state_duty_commission"
STATE_DUTY_2025_CASH_AMOUNT_KEY = "state_duty_2025_cash_amount"
DEFAULT_STATE_DUTY_COMMISSION = Decimal("150")
DEFAULT_STATE_DUTY_2025_CASH_AMOUNT = Decimal("2200")
SPECIAL_STATE_DUTY_BASE = Decimal("2025")


def _decimal(value: object, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


async def _get_setting(db: AsyncSession, key: str, default: Decimal) -> Decimal:
    result = await db.execute(select(AppSetting).where(AppSetting.setting_key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSetting(setting_key=key, setting_value=str(default))
        db.add(row)
        await db.flush()
        return default
    value = _decimal(row.setting_value, default)
    if value < 0:
        return default
    return value


async def get_state_duty_settings(db: AsyncSession) -> dict[str, Decimal]:
    return {
        "commission": await _get_setting(db, STATE_DUTY_COMMISSION_KEY, DEFAULT_STATE_DUTY_COMMISSION),
        "special_2025_cash_amount": await _get_setting(
            db,
            STATE_DUTY_2025_CASH_AMOUNT_KEY,
            DEFAULT_STATE_DUTY_2025_CASH_AMOUNT,
        ),
    }


def calculate_state_duty_cash_amount(base_amount: Decimal, settings: dict[str, Decimal]) -> dict[str, Decimal]:
    base = Decimal(str(base_amount or 0))
    if base <= 0:
        return {"base": Decimal("0"), "commission": Decimal("0"), "cash_amount": Decimal("0")}

    if base == SPECIAL_STATE_DUTY_BASE:
        cash_amount = max(base, settings["special_2025_cash_amount"])
    else:
        cash_amount = base + settings["commission"]

    return {
        "base": base,
        "commission": cash_amount - base,
        "cash_amount": cash_amount,
    }


async def calculate_state_duty_for_order(db: AsyncSession, base_amount: Decimal) -> dict[str, Decimal]:
    settings = await get_state_duty_settings(db)
    return calculate_state_duty_cash_amount(base_amount, settings)


async def update_state_duty_settings(
    db: AsyncSession,
    commission: Decimal,
    special_2025_cash_amount: Decimal,
) -> dict[str, Decimal]:
    if commission < 0:
        raise ServiceError("Комиссия не может быть отрицательной", status_code=400)
    if special_2025_cash_amount < SPECIAL_STATE_DUTY_BASE:
        raise ServiceError("Сумма в кассу для госпошлины 2025 ₽ не может быть меньше 2025 ₽", status_code=400)

    values = {
        STATE_DUTY_COMMISSION_KEY: commission,
        STATE_DUTY_2025_CASH_AMOUNT_KEY: special_2025_cash_amount,
    }
    result = await db.execute(select(AppSetting).where(AppSetting.setting_key.in_(values.keys())))
    existing = {row.setting_key: row for row in result.scalars().all()}
    for key, value in values.items():
        row = existing.get(key)
        if row is None:
            db.add(AppSetting(setting_key=key, setting_value=str(value)))
        else:
            row.setting_value = str(value)
            db.add(row)
    await db.flush()
    return await get_state_duty_settings(db)


def state_duty_settings_to_dict(settings: dict[str, Decimal]) -> dict:
    commission = settings["commission"]
    special = settings["special_2025_cash_amount"]
    return {
        "commission": float(commission),
        "special_2025_cash_amount": float(special),
        "special_2025_commission": float(special - SPECIAL_STATE_DUTY_BASE),
    }
