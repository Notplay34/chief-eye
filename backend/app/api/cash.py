"""API касс и смен: открытие/закрытие смены по павильонам; касса номеров (plate-rows)."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.api.auth import RequireCashAccess, RequirePlateAccess, UserInfo
from app.models import CashRow, CashShift, PlateCashRow, PlatePayout, ShiftStatus
from app.schemas.cash import (
    ShiftOpen, ShiftClose, ShiftResponse, ShiftCurrentResponse,
    CashRowCreate, CashRowUpdate, CashRowResponse,
)
from app.services.errors import ServiceError
from app.services.cash_service import (
    can_manage_pavilion_cash,
    close_shift as close_shift_service,
    get_cash_day_summary as get_cash_day_summary_service,
    get_current_shift_summary as get_current_shift_summary_service,
    get_state_duty_commission_summary as get_state_duty_commission_summary_service,
    _fio_initials,
    PLATE_PAYOUT_INTERMEDIATE,
    PLATE_PAYOUT_TRANSFER,
    open_shift as open_shift_service,
    pay_plate_payouts as pay_plate_payouts_service,
    reconcile_cash_day as reconcile_cash_day_service,
    shift_to_dict,
    transfer_plate_payouts_to_intermediate as transfer_plate_payouts_to_intermediate_service,
    withdraw_state_duty_commissions as withdraw_state_duty_commissions_service,
)
from app.services.warehouse_service import adjust_stock_for_manual_cash_row

logger = get_logger(__name__)
router = APIRouter(prefix="/cash", tags=["cash"])


def _apply_date_filters(query, model, business_date: Optional[date], date_from: Optional[date], date_to: Optional[date]):
    if business_date is not None:
        start = datetime.combine(business_date, time.min)
        return query.where(model.created_at >= start, model.created_at < start + timedelta(days=1))
    if date_from is not None:
        query = query.where(model.created_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.where(model.created_at < datetime.combine(date_to, time.min) + timedelta(days=1))
    return query


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _ensure_pavilion_cash_access(user: UserInfo, pavilion: int) -> None:
    if not can_manage_pavilion_cash(user, pavilion):
        raise HTTPException(status_code=403, detail="Нет доступа к кассе этого павильона")


@router.post("/shifts", response_model=dict)
async def open_shift(
    body: ShiftOpen,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Открыть смену по павильону. Павильон 1 — оператор/менеджер/админ, павильон 2 — оператор изготовления/менеджер/админ."""
    try:
        shift = await open_shift_service(db, user, body.pavilion, body.opening_balance)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Открыта смена павильон=%s", body.pavilion)
    return shift


@router.get("/shifts/current")
async def get_current_shift(
    pavilion: int = Query(..., ge=1, le=2),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Текущая открытая смена по павильону и сумма по ней."""
    try:
        return await get_current_shift_summary_service(db, user, pavilion)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.get("/shifts", response_model=list)
async def list_shifts(
    pavilion: Optional[int] = Query(None, ge=1, le=2),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Список смен (фильтр по павильону и статусу)."""
    q = select(CashShift).order_by(CashShift.opened_at.desc()).limit(limit)
    if pavilion is not None:
        _ensure_pavilion_cash_access(user, pavilion)
        q = q.where(CashShift.pavilion == pavilion)
    else:
        allowed_pavilions = [p for p in (1, 2) if can_manage_pavilion_cash(user, p)]
        if not allowed_pavilions:
            raise HTTPException(status_code=403, detail="Нет доступа к кассам")
        q = q.where(CashShift.pavilion.in_(allowed_pavilions))
    if status is not None:
        try:
            q = q.where(CashShift.status == ShiftStatus(status))
        except ValueError:
            pass
    r = await db.execute(q)
    shifts = r.scalars().all()
    return [shift_to_dict(shift) for shift in shifts]


@router.patch("/shifts/{shift_id}/close", response_model=dict)
async def close_shift(
  shift_id: int,
  body: ShiftClose,
  db: AsyncSession = Depends(get_db),
  user: UserInfo = Depends(RequireCashAccess),
):
    """Закрыть смену (указать посчитанную наличность)."""
    try:
        shift = await close_shift_service(db, user, shift_id, body.closing_balance)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Закрыта смена id=%s", shift_id)
    return shift


# --- Таблица кассы (редактируемые строки: ФИО, заявление, госпошлина, ДКП, страховка, номера, итого) ---

def _cash_row_to_dict(row: CashRow) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "plate_quantity": int(row.plate_quantity or 0),
        "application": float(row.application),
        "state_duty": float(row.state_duty),
        "dkp": float(row.dkp),
        "insurance": float(row.insurance),
        "plates": float(row.plates),
        "total": float(row.total),
        "source_type": row.source_type,
        "source_date": row.source_date.isoformat() if row.source_date else None,
        "source_batch": row.source_batch,
    }


@router.get("/rows", response_model=list)
async def list_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    business_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Список строк таблицы кассы (последние сверху)."""
    _ensure_pavilion_cash_access(user, 1)
    q = select(CashRow).order_by(CashRow.created_at.desc()).limit(limit)
    q = _apply_date_filters(q, CashRow, business_date, date_from, date_to)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [_cash_row_to_dict(row) for row in rows]


@router.post("/rows", response_model=dict)
async def create_cash_row(
    body: CashRowCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Добавить строку в таблицу кассы."""
    _ensure_pavilion_cash_access(user, 1)
    row = CashRow(
        client_name=body.client_name or "",
        plate_quantity=body.plate_quantity,
        application=body.application,
        state_duty=body.state_duty,
        dkp=body.dkp,
        insurance=body.insurance,
        plates=body.plates,
        total=body.total,
    )
    db.add(row)
    try:
        await adjust_stock_for_manual_cash_row(db, body.plate_quantity)
        await db.flush()
    except ServiceError as exc:
        _raise_service_error(exc)
    return _cash_row_to_dict(row)


@router.patch("/rows/{row_id}", response_model=dict)
async def update_cash_row(
    row_id: int,
    body: CashRowUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Обновить ячейки строки кассы (передавать только изменённые поля)."""
    _ensure_pavilion_cash_access(user, 1)
    r = await db.execute(select(CashRow).where(CashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if body.client_name is not None:
        row.client_name = body.client_name
    if body.plate_quantity is not None:
        delta = body.plate_quantity - int(row.plate_quantity or 0)
        try:
            await adjust_stock_for_manual_cash_row(db, delta)
        except ServiceError as exc:
            _raise_service_error(exc)
        row.plate_quantity = body.plate_quantity
    if body.application is not None:
        row.application = body.application
    if body.state_duty is not None:
        row.state_duty = body.state_duty
    if body.dkp is not None:
        row.dkp = body.dkp
    if body.insurance is not None:
        row.insurance = body.insurance
    if body.plates is not None:
        row.plates = body.plates
    if body.total is not None:
        row.total = body.total
    db.add(row)
    await db.flush()
    return _cash_row_to_dict(row)


@router.delete("/rows/{row_id}", status_code=204)
async def delete_cash_row(
    row_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Удалить строку из таблицы кассы."""
    _ensure_pavilion_cash_access(user, 1)
    r = await db.execute(select(CashRow).where(CashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if int(row.plate_quantity or 0) > 0:
        try:
            await adjust_stock_for_manual_cash_row(db, -int(row.plate_quantity or 0))
        except ServiceError as exc:
            _raise_service_error(exc)
    if row.source_type in {PLATE_PAYOUT_INTERMEDIATE, PLATE_PAYOUT_TRANSFER} and row.source_batch:
        await db.execute(
            delete(PlateCashRow).where(
                PlateCashRow.source_type == PLATE_PAYOUT_TRANSFER,
                or_(
                    PlateCashRow.source_batch == row.source_batch,
                    PlateCashRow.source_batch.like(f"{row.source_batch}:%"),
                ),
            )
        )
        payouts = (
            await db.execute(select(PlatePayout).where(PlatePayout.transfer_batch == row.source_batch))
        ).scalars().all()
        for payout in payouts:
            payout.transferred_at = None
            payout.transferred_by_id = None
            payout.transfer_batch = None
            payout.paid_at = None
            payout.paid_by_id = None
            db.add(payout)
    await db.delete(row)
    await db.flush()


# --- Касса номеров: Фамилия и Сумма (под тем же /cash/, чтобы nginx не трогать) ---

class PlateCashRowCreate(BaseModel):
    client_name: str = ""
    amount: float = 0


class CashDayReconcileBody(BaseModel):
    pavilion: int
    business_date: Optional[date] = None
    actual_balance: Decimal
    note: Optional[str] = None


class StateDutyCommissionWithdrawBody(BaseModel):
    business_date: Optional[date] = None


@router.get("/days/current")
async def get_current_cash_day(
    pavilion: int = Query(..., ge=1, le=2),
    business_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Кассовый день: дневной итог по бумажной таблице и статус сверки."""
    try:
        return await get_cash_day_summary_service(db, user, pavilion, business_date)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.post("/days/reconcile")
async def reconcile_cash_day(
    body: CashDayReconcileBody,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Сверить кассовый день: ввести фактическую сумму и получить расхождение."""
    try:
        return await reconcile_cash_day_service(
            db,
            user,
            body.pavilion,
            body.actual_balance,
            body.business_date,
            body.note,
        )
    except ServiceError as exc:
        _raise_service_error(exc)


@router.get("/state-duty-commissions")
async def get_state_duty_commissions(
    business_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    try:
        return await get_state_duty_commission_summary_service(db, user, business_date)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.post("/state-duty-commissions/withdraw")
async def withdraw_state_duty_commissions(
    body: StateDutyCommissionWithdrawBody,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    try:
        return await withdraw_state_duty_commissions_service(db, user, body.business_date)
    except ServiceError as exc:
        _raise_service_error(exc)


class PlateCashRowUpdate(BaseModel):
    client_name: Optional[str] = None
    amount: Optional[float] = None


def _plate_row_to_dict(row: PlateCashRow) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "amount": float(row.amount),
        "source_type": row.source_type,
        "source_date": row.source_date.isoformat() if row.source_date else None,
        "source_batch": row.source_batch,
    }


@router.get("/plate-rows")
async def list_plate_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    business_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Список строк кассы номеров (последние сверху)."""
    q = select(PlateCashRow).order_by(PlateCashRow.created_at.desc()).limit(limit)
    q = _apply_date_filters(q, PlateCashRow, business_date, date_from, date_to)
    r = await db.execute(q)
    rows = r.scalars().all()
    total = sum(float(row.amount) for row in rows)
    return {"rows": [_plate_row_to_dict(row) for row in rows], "total": total}


@router.post("/plate-rows")
async def create_plate_cash_row(
    body: PlateCashRowCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Добавить строку в кассу номеров (сумма может быть отрицательной)."""
    row = PlateCashRow(
        client_name=(body.client_name or "").strip(),
        amount=Decimal(str(body.amount)),
    )
    db.add(row)
    await db.flush()
    return _plate_row_to_dict(row)


@router.patch("/plate-rows/{row_id}")
async def update_plate_cash_row(
    row_id: int,
    body: PlateCashRowUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Обновить строку кассы номеров."""
    r = await db.execute(select(PlateCashRow).where(PlateCashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if body.client_name is not None:
        row.client_name = body.client_name.strip()
    if body.amount is not None:
        row.amount = Decimal(str(body.amount))
    db.add(row)
    await db.flush()
    return _plate_row_to_dict(row)


@router.delete("/plate-rows/{row_id}", status_code=204)
async def delete_plate_cash_row(
    row_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Удалить строку кассы номеров."""
    r = await db.execute(select(PlateCashRow).where(PlateCashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if row.source_type == PLATE_PAYOUT_TRANSFER and row.source_batch:
        payout_id = None
        if ":" in row.source_batch:
            try:
                payout_id = int(row.source_batch.rsplit(":", 1)[1])
            except ValueError:
                payout_id = None
        q = select(PlatePayout)
        if payout_id is not None:
            q = q.where(PlatePayout.id == payout_id)
        else:
            q = q.where(PlatePayout.transfer_batch == row.source_batch)
        payouts = (await db.execute(q)).scalars().all()
        for payout in payouts:
            payout.paid_at = None
            payout.paid_by_id = None
            db.add(payout)
    await db.delete(row)
    await db.flush()


# --- Реестр выдачи денег за номера (пав.1 -> пав.2) ---


def _payout_to_dict(row: PlatePayout) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "client_short_name": _fio_initials(row.client_name),
        "quantity": int(row.quantity or 1),
        "amount": float(row.amount),
        "transferred_at": row.transferred_at.isoformat() if row.transferred_at else None,
        "transferred_by_id": row.transferred_by_id,
        "transfer_batch": row.transfer_batch,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "paid_by_id": row.paid_by_id,
    }


@router.get("/plate-payouts")
async def list_plate_payouts(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Деньги за номера, ещё лежащие в кассе документов."""
    _ensure_pavilion_cash_access(user, 1)
    q = (
        select(PlatePayout)
        .where(PlatePayout.transferred_at.is_(None), PlatePayout.paid_at.is_(None))
        .order_by(PlatePayout.created_at)
    )
    r = await db.execute(q)
    rows = r.scalars().all()
    total = sum((row.amount for row in rows), Decimal("0"))
    quantity = sum((int(row.quantity or 1) for row in rows), 0)
    return {
        "rows": [_payout_to_dict(row) for row in rows],
        "total": float(total),
        "quantity": quantity,
    }


@router.post("/plate-payouts/pay")
async def transfer_plate_payouts_to_intermediate(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """
    Перенести деньги за номера из кассы документов в промежуточную кассу.
    """
    _ensure_pavilion_cash_access(user, 1)
    try:
        result = await transfer_plate_payouts_to_intermediate_service(db, user)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Перенос денег за номера: строк=%s сумма=%s", result["count"], result["total"])
    return result


@router.get("/plate-transfers")
async def list_plate_transfers(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Промежуточная касса номеров: деньги перенесены из кассы документов, но ещё не переданы павильону номеров."""
    _ensure_pavilion_cash_access(user, 1)
    q = (
        select(PlatePayout)
        .where(PlatePayout.transferred_at.is_not(None), PlatePayout.paid_at.is_(None))
        .order_by(PlatePayout.transferred_at, PlatePayout.created_at)
    )
    r = await db.execute(q)
    rows = r.scalars().all()
    total = sum((row.amount for row in rows), Decimal("0"))
    quantity = sum((int(row.quantity or 1) for row in rows), 0)
    return {
        "rows": [_payout_to_dict(row) for row in rows],
        "total": float(total),
        "quantity": quantity,
    }


@router.post("/plate-transfers/pay")
async def pay_plate_transfers(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Передать деньги из промежуточной кассы в павильон номеров."""
    _ensure_pavilion_cash_access(user, 1)
    try:
        result = await pay_plate_payouts_service(db, user)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Передача денег в павильон номеров: строк=%s сумма=%s", result["count"], result["total"])
    return result
