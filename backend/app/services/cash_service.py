"""Cash and shift domain logic."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import UserInfo
from app.models import CashRow, CashShift, Payment, PlateCashRow, PlatePayout, ShiftStatus
from app.models.employee import EmployeeRole
from app.services.errors import ServiceError


def shift_to_dict(shift: CashShift) -> dict:
    return {
        "id": shift.id,
        "pavilion": shift.pavilion,
        "opened_by_id": shift.opened_by_id,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else "",
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "closed_by_id": shift.closed_by_id,
        "opening_balance": float(shift.opening_balance),
        "closing_balance": float(shift.closing_balance) if shift.closing_balance is not None else None,
        "status": shift.status.value,
    }


async def get_current_shift(db: AsyncSession, pavilion: int) -> Optional[CashShift]:
    query = (
        select(CashShift)
        .where(CashShift.pavilion == pavilion, CashShift.status == ShiftStatus.OPEN)
        .order_by(CashShift.opened_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalar_one_or_none()


def _workday_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


async def current_shift_id(db: AsyncSession, pavilion: int) -> Optional[int]:
    shift = await get_current_shift(db, pavilion)
    return shift.id if shift else None


async def ensure_workday_shift(db: AsyncSession, pavilion: int, user: UserInfo) -> CashShift:
    """Return today's active cash bucket for pavilion, creating it lazily when needed."""
    now = datetime.utcnow()
    start, end = _workday_bounds(now)
    today_query = (
        select(CashShift)
        .where(
            CashShift.pavilion == pavilion,
            CashShift.status == ShiftStatus.OPEN,
            CashShift.opened_at >= start,
            CashShift.opened_at < end,
        )
        .order_by(CashShift.opened_at.desc())
        .limit(1)
    )
    today_shift = (await db.execute(today_query)).scalar_one_or_none()
    if today_shift is not None:
        return today_shift

    old_open_query = select(CashShift).where(
        CashShift.pavilion == pavilion,
        CashShift.status == ShiftStatus.OPEN,
    )
    old_open_shifts = (await db.execute(old_open_query)).scalars().all()
    for shift in old_open_shifts:
        shift.status = ShiftStatus.CLOSED
        shift.closed_at = now
        shift.closed_by_id = user.id
        if shift.closing_balance is None:
            shift.closing_balance = shift.opening_balance
        db.add(shift)

    shift = CashShift(
        pavilion=pavilion,
        opened_by_id=user.id,
        opening_balance=Decimal("0"),
        status=ShiftStatus.OPEN,
    )
    db.add(shift)
    await db.flush()
    return shift


def can_manage_pavilion_cash(user: UserInfo, pavilion: int) -> bool:
    try:
        role = EmployeeRole(user.role)
    except ValueError:
        return False
    if pavilion == 1:
        return role in (EmployeeRole.ROLE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN)
    return role in (EmployeeRole.ROLE_PLATE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN)


async def open_shift(db: AsyncSession, user: UserInfo, pavilion: int, opening_balance: Decimal) -> dict:
    if not can_manage_pavilion_cash(user, pavilion):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)
    current = await get_current_shift(db, pavilion)
    if current:
        raise ServiceError(
            f"Смена павильона {pavilion} уже открыта (id={current.id}). Сначала закройте её.",
            status_code=400,
        )
    shift = CashShift(
        pavilion=pavilion,
        opened_by_id=user.id,
        opening_balance=opening_balance,
        status=ShiftStatus.OPEN,
    )
    db.add(shift)
    await db.flush()
    return {"id": shift.id, "pavilion": shift.pavilion, "opened_at": shift.opened_at.isoformat(), "status": "OPEN"}


async def get_current_shift_summary(db: AsyncSession, user: UserInfo, pavilion: int) -> dict:
    if not can_manage_pavilion_cash(user, pavilion):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)
    shift = await get_current_shift(db, pavilion)
    if shift is None:
        return {"shift": None, "total_in_shift": 0}
    total_query = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.shift_id == shift.id)
    total = (await db.execute(total_query)).scalar_one() or Decimal("0")
    return {"shift": shift_to_dict(shift), "total_in_shift": float(total)}


async def close_shift(db: AsyncSession, user: UserInfo, shift_id: int, closing_balance: Decimal) -> dict:
    shift = (await db.execute(select(CashShift).where(CashShift.id == shift_id))).scalar_one_or_none()
    if shift is None:
        raise ServiceError("Смена не найдена", status_code=404)
    if shift.status != ShiftStatus.OPEN:
        raise ServiceError("Смена уже закрыта", status_code=400)
    if not can_manage_pavilion_cash(user, shift.pavilion):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)
    shift.closed_at = datetime.utcnow()
    shift.closed_by_id = user.id
    shift.closing_balance = closing_balance
    shift.status = ShiftStatus.CLOSED
    db.add(shift)
    await db.flush()
    return shift_to_dict(shift)


async def pay_plate_payouts(db: AsyncSession, user: UserInfo) -> dict:
    result = await db.execute(
        select(PlatePayout).where(PlatePayout.paid_at.is_(None)).order_by(PlatePayout.created_at)
    )
    payouts = result.scalars().all()
    if not payouts:
        raise ServiceError("Нет номеров к выдаче", status_code=400)

    total: Decimal = sum((payout.amount for payout in payouts), Decimal("0"))
    if total <= 0:
        raise ServiceError("Сумма к выдаче нулевая", status_code=400)

    db.add(
        CashRow(
            client_name="Номера — выдача",
            application=Decimal("0"),
            state_duty=Decimal("0"),
            dkp=Decimal("0"),
            insurance=Decimal("0"),
            plates=-total,
            total=-total,
        )
    )

    now = datetime.utcnow()
    for payout in payouts:
        db.add(PlateCashRow(client_name=payout.client_name, amount=payout.amount))
        payout.paid_at = now
        payout.paid_by_id = user.id
        db.add(payout)

    await db.flush()
    return {"count": len(payouts), "total": float(total)}
