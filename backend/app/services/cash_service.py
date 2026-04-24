"""Cash and shift/domain-day cash logic."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import UserInfo
from app.models import CashDayReconciliation, CashRow, CashShift, Order, Payment, PlateCashRow, PlatePayout, ShiftStatus
from app.models.payment import PaymentType
from app.models.employee import EmployeeRole
from app.services.audit_service import write_audit_log
from app.services.errors import ServiceError

STATE_DUTY_COMMISSION_WITHDRAWAL = "STATE_DUTY_COMMISSION_WITHDRAWAL"


def _fio_initials(value: str | None) -> str:
    if not value:
        return ""
    parts = [part for part in str(value).split() if part]
    if len(parts) < 2:
        return str(value).strip()
    suffix = ""
    if len(parts) >= 3 and parts[-1].lower().replace("ё", "е") in {"оглы", "кызы"}:
        suffix = " " + parts[-1].lower()
        parts = parts[:-1]
    initials = "".join(f"{part[0]}." for part in parts[1:] if part)
    return f"{parts[0]} {initials}{suffix}".strip()


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


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def _state_duty_commission_from_order(order: Order) -> Decimal:
    form_data = order.form_data or {}
    return Decimal(str(form_data.get("state_duty_commission") or 0))


def _workday_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


def _reconciliation_to_dict(row: CashDayReconciliation | None) -> Optional[dict]:
    if row is None:
        return None
    return {
        "id": row.id,
        "pavilion": row.pavilion,
        "business_date": row.business_date.isoformat(),
        "program_total": float(row.program_total),
        "actual_balance": float(row.actual_balance),
        "difference": float(row.difference),
        "reconciled_by_id": row.reconciled_by_id,
        "reconciled_at": row.reconciled_at.isoformat() if row.reconciled_at else "",
        "note": row.note,
    }


async def _cash_day_program_total(db: AsyncSession, pavilion: int, business_date: date) -> Decimal:
    start, end = _day_bounds(business_date)
    if pavilion == 1:
        query = select(func.coalesce(func.sum(CashRow.total), 0)).where(
            CashRow.created_at >= start,
            CashRow.created_at < end,
        )
    elif pavilion == 2:
        query = select(func.coalesce(func.sum(PlateCashRow.amount), 0)).where(
            PlateCashRow.created_at >= start,
            PlateCashRow.created_at < end,
        )
    else:
        raise ServiceError("Павильон должен быть 1 или 2", status_code=400)
    return (await db.execute(query)).scalar_one() or Decimal("0")


async def get_cash_day_summary(db: AsyncSession, user: UserInfo, pavilion: int, business_date: Optional[date] = None) -> dict:
    if not can_manage_pavilion_cash(user, pavilion):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)

    day = business_date or datetime.utcnow().date()
    program_total = await _cash_day_program_total(db, pavilion, day)
    reconciliation = (
        await db.execute(
            select(CashDayReconciliation).where(
                CashDayReconciliation.pavilion == pavilion,
                CashDayReconciliation.business_date == day,
            )
        )
    ).scalar_one_or_none()
    if reconciliation is None:
        status = "not_reconciled"
        difference = None
    elif reconciliation.difference == 0:
        status = "reconciled"
        difference = Decimal("0")
    else:
        status = "difference"
        difference = reconciliation.actual_balance - program_total

    return {
        "pavilion": pavilion,
        "business_date": day.isoformat(),
        "program_total": float(program_total),
        "status": status,
        "difference": float(difference) if difference is not None else None,
        "reconciliation": _reconciliation_to_dict(reconciliation),
    }


async def get_state_duty_commission_summary(
    db: AsyncSession,
    user: UserInfo,
    business_date: Optional[date] = None,
) -> dict:
    if not can_manage_pavilion_cash(user, 1):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)

    day = business_date or datetime.utcnow().date()
    start, end = _day_bounds(day)
    paid_orders_query = (
        select(Order)
        .join(Payment, Payment.order_id == Order.id)
        .where(
            Payment.type == PaymentType.STATE_DUTY,
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .distinct()
    )
    orders = (await db.execute(paid_orders_query)).scalars().all()
    total = sum((_state_duty_commission_from_order(order) for order in orders), Decimal("0"))
    withdrawal = (
        await db.execute(
            select(CashRow).where(
                CashRow.source_type == STATE_DUTY_COMMISSION_WITHDRAWAL,
                CashRow.source_date == day,
            )
        )
    ).scalar_one_or_none()

    return {
        "business_date": day.isoformat(),
        "commission_total": float(total),
        "withdrawn": withdrawal is not None,
        "withdrawn_row_id": withdrawal.id if withdrawal else None,
        "withdrawn_at": withdrawal.created_at.isoformat() if withdrawal and withdrawal.created_at else None,
        "can_withdraw": total > 0 and withdrawal is None,
    }


async def withdraw_state_duty_commissions(
    db: AsyncSession,
    user: UserInfo,
    business_date: Optional[date] = None,
) -> dict:
    summary = await get_state_duty_commission_summary(db, user, business_date)
    day = date.fromisoformat(summary["business_date"])
    if summary["withdrawn"]:
        return summary
    total = Decimal(str(summary["commission_total"]))
    if total <= 0:
        raise ServiceError("За выбранный день нет комиссий госпошлин к списанию", status_code=400)

    row = CashRow(
        client_name=f"Комиссии госпошлин {day.strftime('%d.%m.%Y')}",
        application=Decimal("0"),
        state_duty=-total,
        dkp=Decimal("0"),
        insurance=Decimal("0"),
        plates=Decimal("0"),
        total=-total,
        source_type=STATE_DUTY_COMMISSION_WITHDRAWAL,
        source_date=day,
    )
    db.add(row)
    await db.flush()
    await write_audit_log(
        db,
        user=user,
        event_type="state_duty_commissions_withdrawn",
        entity_type="cash_row",
        entity_id=row.id,
        payload={"business_date": day.isoformat(), "amount": float(total)},
    )
    return await get_state_duty_commission_summary(db, user, day)


async def reconcile_cash_day(
    db: AsyncSession,
    user: UserInfo,
    pavilion: int,
    actual_balance: Decimal,
    business_date: Optional[date] = None,
    note: Optional[str] = None,
) -> dict:
    if actual_balance < 0:
        raise ServiceError("Фактическая сумма не может быть отрицательной", status_code=400)
    if not can_manage_pavilion_cash(user, pavilion):
        raise ServiceError("Нет доступа к кассе этого павильона", status_code=403)

    day = business_date or datetime.utcnow().date()
    program_total = await _cash_day_program_total(db, pavilion, day)
    difference = actual_balance - program_total
    result = await db.execute(
        select(CashDayReconciliation).where(
            CashDayReconciliation.pavilion == pavilion,
            CashDayReconciliation.business_date == day,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = CashDayReconciliation(
            pavilion=pavilion,
            business_date=day,
            program_total=program_total,
            actual_balance=actual_balance,
            difference=difference,
            reconciled_by_id=user.id,
            note=note,
        )
    else:
        row.program_total = program_total
        row.actual_balance = actual_balance
        row.difference = difference
        row.reconciled_by_id = user.id
        row.reconciled_at = datetime.utcnow()
        row.note = note
    db.add(row)
    await db.flush()
    await write_audit_log(
        db,
        user=user,
        event_type="cash_day_reconciled",
        entity_type="cash_day",
        entity_id=row.id,
        payload={
            "pavilion": pavilion,
            "business_date": day.isoformat(),
            "program_total": float(program_total),
            "actual_balance": float(actual_balance),
            "difference": float(difference),
        },
    )
    return await get_cash_day_summary(db, user, pavilion, day)


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

    payout_names = [
        _fio_initials(payout.client_name)
        for payout in payouts
        if payout.client_name and payout.client_name.strip()
    ]
    cash_row_name = ", ".join(payout_names) if payout_names else "Номера — выдача"

    db.add(
        CashRow(
            client_name=cash_row_name,
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
        db.add(PlateCashRow(client_name=_fio_initials(payout.client_name), amount=payout.amount))
        payout.paid_at = now
        payout.paid_by_id = user.id
        db.add(payout)

    await db.flush()
    await write_audit_log(
        db,
        user=user,
        event_type="plate_payouts_paid",
        entity_type="plate_payout_batch",
        entity_id=None,
        payload={
            "count": len(payouts),
            "total": float(total),
            "order_ids": [payout.order_id for payout in payouts],
        },
    )
    return {"count": len(payouts), "total": float(total)}
