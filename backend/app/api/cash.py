"""API касс и смен: открытие/закрытие смены по павильонам; касса номеров (plate-rows)."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.time_utils import business_day_bounds_utc, business_today, utc_now
from app.api.auth import RequireCashAccess, RequirePlateAccess, UserInfo
from app.models import (
    CashRow,
    CashShift,
    IntermediatePlateTransfer,
    Order,
    OrderStatus,
    Payment,
    PaymentType,
    PlateCashRow,
    PlatePayout,
    ShiftStatus,
)
from app.schemas.cash import (
    ShiftOpen, ShiftClose, ShiftResponse, ShiftCurrentResponse,
    CashRowCreate, CashRowUpdate, CashRowResponse,
)
from app.services.audit_service import write_audit_log
from app.services.errors import ServiceError
from app.services.cash_service import (
    ORDER_PAYMENT_CASH_ROW,
    ORDER_PLATE_EXTRA_CASH_ROW,
    can_manage_pavilion_cash,
    close_shift as close_shift_service,
    get_cash_day_summary as get_cash_day_summary_service,
    get_current_shift_summary as get_current_shift_summary_service,
    get_state_duty_commission_summary as get_state_duty_commission_summary_service,
    _fio_initials,
    list_open_plate_payouts as list_open_plate_payouts_service,
    PLATE_PAYOUT_INTERMEDIATE,
    PLATE_PAYOUT_TRANSFER,
    open_shift as open_shift_service,
    pay_plate_payouts as pay_plate_payouts_service,
    reconcile_cash_day as reconcile_cash_day_service,
    shift_to_dict,
    transfer_plate_payouts_to_intermediate as transfer_plate_payouts_to_intermediate_service,
    withdraw_state_duty_commissions as withdraw_state_duty_commissions_service,
)
from app.services.warehouse_service import (
    ORDER_ROLLBACK,
    adjust_stock_for_plate_cash_row,
    get_or_create_stock,
    plate_quantity_from_order,
    record_stock_movement,
    release_reservation_for_order,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/cash", tags=["cash"])
PLATE_CASH_UNIT_PRICE = Decimal("1500")


def _apply_date_filters(query, model, business_date: Optional[date], date_from: Optional[date], date_to: Optional[date]):
    if business_date is not None:
        start, end = business_day_bounds_utc(business_date)
        return query.where(model.created_at >= start, model.created_at < end)
    if date_from is not None:
        query = query.where(model.created_at >= business_day_bounds_utc(date_from)[0])
    if date_to is not None:
        query = query.where(model.created_at < business_day_bounds_utc(date_to)[1])
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


def _cash_row_order_id(row: CashRow) -> Optional[int]:
    if row.source_type not in {ORDER_PAYMENT_CASH_ROW, ORDER_PLATE_EXTRA_CASH_ROW} or not row.source_batch:
        return None
    try:
        return int(row.source_batch)
    except ValueError:
        return None


async def _reduce_intermediate_cash_row(db: AsyncSession, batch: str, amount: Decimal) -> None:
    transfer_row = (
        await db.execute(
            select(CashRow).where(
                CashRow.source_type == PLATE_PAYOUT_INTERMEDIATE,
                CashRow.source_batch == batch,
            )
        )
    ).scalar_one_or_none()
    if not transfer_row:
        return
    transfer_row.plates = Decimal(str(transfer_row.plates or 0)) + amount
    transfer_row.total = Decimal(str(transfer_row.total or 0)) + amount
    if transfer_row.plates == 0 and transfer_row.total == 0:
        await db.delete(transfer_row)
    else:
        db.add(transfer_row)


async def _reduce_plate_cash_rows(db: AsyncSession, payout: PlatePayout, amount: Decimal) -> None:
    if not payout.transfer_batch:
        return
    rows = (
        await db.execute(
            select(PlateCashRow)
            .where(
                PlateCashRow.source_type == PLATE_PAYOUT_TRANSFER,
                or_(
                    PlateCashRow.source_batch == payout.transfer_batch,
                    PlateCashRow.source_batch == f"{payout.transfer_batch}:{payout.id}",
                ),
            )
            .order_by(PlateCashRow.created_at.desc(), PlateCashRow.id.desc())
        )
    ).scalars().all()
    remaining = amount
    for plate_row in rows:
        if remaining <= 0:
            break
        plate_row_amount = Decimal(str(plate_row.amount or 0))
        if plate_row_amount <= remaining:
            remaining -= plate_row_amount
            await db.delete(plate_row)
        else:
            plate_row.amount = plate_row_amount - remaining
            remaining = Decimal("0")
            db.add(plate_row)


async def _remove_plate_payout_for_cash_row(db: AsyncSession, row: CashRow) -> None:
    amount = Decimal(str(row.plates or 0))
    if amount <= 0:
        return

    q = select(PlatePayout)
    order_id = _cash_row_order_id(row)

    if order_id is not None:
        q = q.where(PlatePayout.order_id == order_id)
    else:
        q = q.where(PlatePayout.client_name == (row.client_name or ""))

    payouts = (await db.execute(q.order_by(PlatePayout.created_at, PlatePayout.id))).scalars().all()
    if not payouts:
        return

    if order_id is None and len(payouts) != 1:
        return

    remaining = amount
    for payout in payouts:
        if remaining <= 0:
            break
        payout_amount = Decimal(str(payout.amount or 0))
        take = payout_amount if payout_amount <= remaining else remaining
        if payout.transfer_batch:
            await _reduce_intermediate_cash_row(db, payout.transfer_batch, take)
            await _reduce_plate_cash_rows(db, payout, take)
        if payout_amount <= take:
            remaining -= payout_amount
            await db.delete(payout)
        else:
            payout.amount = payout_amount - take
            remaining = Decimal("0")
            db.add(payout)


async def _rollback_order_payment_for_cash_row(db: AsyncSession, row: CashRow) -> None:
    order_id = _cash_row_order_id(row)
    if order_id is None:
        return

    if row.source_type == ORDER_PAYMENT_CASH_ROW:
        await db.execute(
            delete(Payment).where(
                Payment.order_id == order_id,
                Payment.type.in_([PaymentType.STATE_DUTY, PaymentType.INCOME_PAVILION1]),
            )
        )
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if order and order.status in {
            OrderStatus.PAID,
            OrderStatus.PLATE_IN_PROGRESS,
            OrderStatus.PLATE_READY,
            OrderStatus.COMPLETED,
        }:
            if order.status in {OrderStatus.PLATE_IN_PROGRESS, OrderStatus.PLATE_READY}:
                await release_reservation_for_order(db, order.id)
            elif order.status == OrderStatus.COMPLETED and order.need_plate:
                stock = await get_or_create_stock(db)
                quantity = plate_quantity_from_order(order)
                stock.quantity += quantity
                db.add(stock)
                await record_stock_movement(
                    db,
                    movement_type=ORDER_ROLLBACK,
                    quantity_delta=quantity,
                    balance_after=stock.quantity,
                    source_type="order",
                    source_id=order.id,
                    note="Откат оплаты заказа",
                )
            order.status = OrderStatus.AWAITING_PAYMENT
            db.add(order)
    elif row.source_type == ORDER_PLATE_EXTRA_CASH_ROW:
        payment = (
            await db.execute(
                select(Payment)
                .where(
                    Payment.order_id == order_id,
                    Payment.type == PaymentType.INCOME_PAVILION2,
                    Payment.amount == Decimal(str(row.plates or 0)),
                )
                .order_by(Payment.created_at.desc(), Payment.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if payment:
            await db.delete(payment)


@router.get("/rows", response_model=list)
async def list_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0, le=100000),
    business_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Список строк таблицы кассы (последние сверху)."""
    _ensure_pavilion_cash_access(user, 1)
    q = select(CashRow).order_by(CashRow.created_at.desc()).offset(offset).limit(limit)
    q = _apply_date_filters(q, CashRow, business_date, date_from, date_to)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [_cash_row_to_dict(row) for row in rows]


@router.get("/rows/balance", response_model=dict)
async def get_cash_rows_balance(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Фактический остаток кассы документов сейчас: сумма всего журнала."""
    _ensure_pavilion_cash_access(user, 1)
    q = select(func.coalesce(func.sum(CashRow.total), 0))
    total = (await db.execute(q)).scalar_one() or Decimal("0")
    return {
        "business_date": None,
        "balance": float(total),
    }


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
        application=body.application,
        state_duty=body.state_duty,
        dkp=body.dkp,
        insurance=body.insurance,
        plates=body.plates,
        total=body.total,
    )
    db.add(row)
    await db.flush()
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
    fields_set = getattr(body, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(body, "__fields_set__", set())
    if row.source_type:
        forbidden_fields = {"state_duty", "plates", "total"} & set(fields_set)
        if forbidden_fields:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Системная строка связана с оплатой или переносом. "
                    "Можно менять только ФИО, заявление, ДКП и страховку."
                ),
            )
    if body.client_name is not None:
        row.client_name = body.client_name
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
    elif row.source_type and {"application", "dkp", "insurance"} & set(fields_set):
        row.total = (
            Decimal(str(row.application or 0))
            + Decimal(str(row.state_duty or 0))
            + Decimal(str(row.dkp or 0))
            + Decimal(str(row.insurance or 0))
            + Decimal(str(row.plates or 0))
        )
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
    await _remove_plate_payout_for_cash_row(db, row)
    await _rollback_order_payment_for_cash_row(db, row)
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
    quantity: int = Field(default=0, ge=0, le=100)
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
    quantity: Optional[int] = Field(default=None, ge=0, le=100)
    amount: Optional[float] = None


class ManualPlateTransferCreate(BaseModel):
    client_name: str = ""
    quantity: int = Field(default=0, ge=0, le=100)
    amount: Decimal = Field(default=Decimal("0"), ge=0)


class ManualPlateTransferUpdate(BaseModel):
    client_name: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=0, le=100)
    amount: Optional[Decimal] = Field(default=None, ge=0)


def _plate_row_to_dict(row: PlateCashRow) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "quantity": int(row.quantity or 0),
        "amount": float(row.amount),
        "source_type": row.source_type,
        "source_date": row.source_date.isoformat() if row.source_date else None,
        "source_batch": row.source_batch,
    }


def _plate_cash_row_controls_stock(row: PlateCashRow) -> bool:
    return not row.source_type


@router.get("/plate-rows")
async def list_plate_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0, le=100000),
    business_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Список строк кассы номеров (последние сверху)."""
    base_q = _apply_date_filters(select(PlateCashRow), PlateCashRow, business_date, date_from, date_to)
    total_q = _apply_date_filters(
        select(func.coalesce(func.sum(PlateCashRow.amount), 0)),
        PlateCashRow,
        business_date,
        date_from,
        date_to,
    )
    q = base_q.order_by(PlateCashRow.created_at.desc()).offset(offset).limit(limit)
    r = await db.execute(q)
    rows = r.scalars().all()
    total = (await db.execute(total_q)).scalar_one() or Decimal("0")
    return {"rows": [_plate_row_to_dict(row) for row in rows], "total": float(total)}


@router.post("/plate-rows")
async def create_plate_cash_row(
    body: PlateCashRowCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Добавить строку в кассу номеров (сумма может быть отрицательной)."""
    amount = PLATE_CASH_UNIT_PRICE * body.quantity if body.quantity > 0 else Decimal(str(body.amount))
    row = PlateCashRow(
        client_name=(body.client_name or "").strip(),
        quantity=body.quantity,
        amount=amount,
    )
    db.add(row)
    try:
        await adjust_stock_for_plate_cash_row(db, body.quantity)
        await db.flush()
    except ServiceError as exc:
        _raise_service_error(exc)
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
    if body.quantity is not None:
        delta = body.quantity - int(row.quantity or 0)
        if _plate_cash_row_controls_stock(row):
            try:
                await adjust_stock_for_plate_cash_row(db, delta)
            except ServiceError as exc:
                _raise_service_error(exc)
        row.quantity = body.quantity
    if body.amount is not None:
        row.amount = Decimal(str(body.amount))
    if int(row.quantity or 0) > 0:
        row.amount = PLATE_CASH_UNIT_PRICE * int(row.quantity or 0)
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
    if _plate_cash_row_controls_stock(row) and int(row.quantity or 0) > 0:
        try:
            await adjust_stock_for_plate_cash_row(db, -int(row.quantity or 0))
        except ServiceError as exc:
            _raise_service_error(exc)
    await db.delete(row)
    await db.flush()


# --- Реестр выдачи денег за номера (пав.1 -> пав.2) ---


def _payout_to_dict(row: PlatePayout) -> dict:
    return {
        "row_type": "auto",
        "row_key": f"auto:{row.id}",
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


def _payout_transfer_to_dict(row: PlatePayout, order_status: OrderStatus) -> dict:
    data = _payout_to_dict(row)
    data["order_status"] = order_status.value
    data["ready_to_pay"] = order_status == OrderStatus.COMPLETED
    return data


def _manual_transfer_to_dict(row: IntermediatePlateTransfer) -> dict:
    return {
        "row_type": "manual",
        "row_key": f"manual:{row.id}",
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "client_short_name": _fio_initials(row.client_name) or row.client_name,
        "quantity": int(row.quantity or 0),
        "amount": float(row.amount),
        "transferred_at": row.created_at.isoformat() if row.created_at else None,
        "transferred_by_id": row.created_by_id,
        "transfer_batch": None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "paid_by_id": row.paid_by_id,
        "ready_to_pay": Decimal(str(row.amount or 0)) > 0,
    }


def _transfer_history_to_dict(row: PlatePayout | IntermediatePlateTransfer) -> dict:
    row_type = "manual" if isinstance(row, IntermediatePlateTransfer) else "auto"
    return {
        "row_type": row_type,
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "client_short_name": _fio_initials(row.client_name) or row.client_name,
        "quantity": int(row.quantity or 0),
        "amount": float(row.amount),
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "paid_by_id": row.paid_by_id,
    }


def _history_day_label(day: str) -> str:
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return day
    return parsed.strftime("%d.%m.%Y")


@router.get("/plate-payouts")
async def list_plate_payouts(
    business_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Деньги за номера, ещё лежащие в кассе документов."""
    _ensure_pavilion_cash_access(user, 1)
    day = business_date or business_today()
    rows = await list_open_plate_payouts_service(db, day)
    total = sum((row.amount for row in rows), Decimal("0"))
    quantity = sum((int(row.quantity or 1) for row in rows), 0)
    return {
        "rows": [_payout_to_dict(row) for row in rows],
        "total": float(total),
        "quantity": quantity,
        "business_date": day.isoformat(),
    }


@router.post("/plate-payouts/pay")
async def transfer_plate_payouts_to_intermediate(
    business_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """
    Перенести деньги за номера из кассы документов в промежуточную кассу.
    """
    _ensure_pavilion_cash_access(user, 1)
    try:
        result = await transfer_plate_payouts_to_intermediate_service(db, user, business_date)
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
        select(PlatePayout, Order.status)
        .join(Order, Order.id == PlatePayout.order_id)
        .where(PlatePayout.transferred_at.is_not(None), PlatePayout.paid_at.is_(None))
        .order_by(PlatePayout.transferred_at, PlatePayout.created_at)
    )
    r = await db.execute(q)
    payout_rows = r.all()
    manual_rows = (
        await db.execute(
            select(IntermediatePlateTransfer)
            .where(IntermediatePlateTransfer.paid_at.is_(None))
            .order_by(IntermediatePlateTransfer.created_at, IntermediatePlateTransfer.id)
        )
    ).scalars().all()
    rows = [_payout_transfer_to_dict(row, status) for row, status in payout_rows] + [_manual_transfer_to_dict(row) for row in manual_rows]
    total = sum((Decimal(str(row["amount"])) for row in rows), Decimal("0"))
    quantity = sum((int(row["quantity"] or 0) for row in rows), 0)
    ready_rows = [row for row in rows if row.get("ready_to_pay")]
    ready_total = sum((Decimal(str(row["amount"])) for row in ready_rows), Decimal("0"))
    ready_quantity = sum((int(row["quantity"] or 0) for row in ready_rows), 0)
    return {
        "rows": rows,
        "total": float(total),
        "quantity": quantity,
        "ready_total": float(ready_total),
        "ready_quantity": ready_quantity,
        "ready_count": len(ready_rows),
    }


@router.get("/plate-transfers/history")
async def list_plate_transfer_history(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """История денег, выданных из промежуточной кассы в кассу номеров."""
    _ensure_pavilion_cash_access(user, 1)
    payout_rows = (
        await db.execute(
            select(PlatePayout)
            .where(
                PlatePayout.transferred_at.is_not(None),
                PlatePayout.paid_at.is_not(None),
                or_(PlatePayout.transfer_batch.is_(None), ~PlatePayout.transfer_batch.like("deleted:%")),
            )
            .order_by(PlatePayout.paid_at.desc(), PlatePayout.id.desc())
            .limit(limit + offset)
        )
    ).scalars().all()
    manual_rows = (
        await db.execute(
            select(IntermediatePlateTransfer)
            .where(IntermediatePlateTransfer.paid_at.is_not(None))
            .order_by(IntermediatePlateTransfer.paid_at.desc(), IntermediatePlateTransfer.id.desc())
            .limit(limit + offset)
        )
    ).scalars().all()
    rows = [_transfer_history_to_dict(row) for row in payout_rows] + [_transfer_history_to_dict(row) for row in manual_rows]
    rows.sort(key=lambda row: row.get("paid_at") or "", reverse=True)
    rows = rows[offset:offset + limit]
    total = sum((Decimal(str(row["amount"])) for row in rows), Decimal("0"))
    quantity = sum((int(row["quantity"] or 0) for row in rows), 0)
    days_by_key: dict[str, dict] = {}
    for row in rows:
        day_key = (row.get("paid_at") or "")[:10] or "unknown"
        if day_key not in days_by_key:
            days_by_key[day_key] = {
                "date": day_key,
                "label": _history_day_label(day_key),
                "rows": [],
                "total": 0.0,
                "quantity": 0,
                "count": 0,
            }
        day = days_by_key[day_key]
        day["rows"].append(row)
        day["total"] = float(Decimal(str(day["total"])) + Decimal(str(row["amount"])))
        day["quantity"] += int(row["quantity"] or 0)
        day["count"] += 1
    days = list(days_by_key.values())
    days.sort(key=lambda item: item["date"], reverse=True)
    return {"rows": rows, "days": days, "total": float(total), "quantity": quantity}


@router.post("/plate-transfers/manual")
async def create_manual_plate_transfer(
    body: ManualPlateTransferCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Добавить ручную строку в промежуточную кассу номеров."""
    _ensure_pavilion_cash_access(user, 1)
    row = IntermediatePlateTransfer(
        client_name=(body.client_name or "").strip(),
        quantity=body.quantity,
        amount=body.amount,
        created_by_id=user.id,
    )
    db.add(row)
    await db.flush()
    await write_audit_log(
        db,
        user=user,
        event_type="manual_plate_transfer_created",
        entity_type="intermediate_plate_transfer",
        entity_id=row.id,
        payload={"client_name": row.client_name, "quantity": row.quantity, "amount": float(row.amount)},
    )
    return _manual_transfer_to_dict(row)


@router.patch("/plate-transfers/manual/{row_id}")
async def update_manual_plate_transfer(
    row_id: int,
    body: ManualPlateTransferUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Обновить ручную строку промежуточной кассы."""
    _ensure_pavilion_cash_access(user, 1)
    row = (
        await db.execute(
            select(IntermediatePlateTransfer).where(
                IntermediatePlateTransfer.id == row_id,
                IntermediatePlateTransfer.paid_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if body.client_name is not None:
        row.client_name = body.client_name.strip()
    if body.quantity is not None:
        row.quantity = body.quantity
    if body.amount is not None:
        row.amount = body.amount
    db.add(row)
    await db.flush()
    return _manual_transfer_to_dict(row)


@router.delete("/plate-transfers/{row_key}", status_code=204)
async def delete_plate_transfer_row(
    row_key: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Удалить строку из промежуточной кассы без возврата в кассу документов."""
    _ensure_pavilion_cash_access(user, 1)
    if ":" not in row_key:
        raise HTTPException(status_code=400, detail="Некорректная строка")
    row_type, raw_id = row_key.split(":", 1)
    try:
        row_id = int(raw_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная строка")

    if row_type == "manual":
        row = (
            await db.execute(
                select(IntermediatePlateTransfer).where(
                    IntermediatePlateTransfer.id == row_id,
                    IntermediatePlateTransfer.paid_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Строка не найдена")
        await write_audit_log(
            db,
            user=user,
            event_type="manual_plate_transfer_deleted",
            entity_type="intermediate_plate_transfer",
            entity_id=row.id,
            payload={"client_name": row.client_name, "quantity": row.quantity, "amount": float(row.amount)},
        )
        await db.delete(row)
        await db.flush()
        return

    if row_type == "auto":
        payout = (
            await db.execute(
                select(PlatePayout).where(
                    PlatePayout.id == row_id,
                    PlatePayout.transferred_at.is_not(None),
                    PlatePayout.paid_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if payout is None:
            raise HTTPException(status_code=404, detail="Строка не найдена")
        payout.paid_at = utc_now()
        payout.paid_by_id = user.id
        payout.transfer_batch = f"deleted:{payout.transfer_batch or payout.id}"
        db.add(payout)
        await write_audit_log(
            db,
            user=user,
            event_type="plate_transfer_deleted",
            entity_type="plate_payout",
            entity_id=payout.id,
            payload={"order_id": payout.order_id, "amount": float(payout.amount), "quantity": payout.quantity},
        )
        await db.flush()
        return

    raise HTTPException(status_code=400, detail="Некорректная строка")


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
