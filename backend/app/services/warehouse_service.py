"""Warehouse domain logic for plate stock and reservations."""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderStatus, PlateDefect, PlateReservation, PlateStock, PlateStockMovement
from app.services.errors import ServiceError

STOCK_IN = "STOCK_IN"
ORDER_COMPLETED = "ORDER_COMPLETED"
PLATE_CASH_SALE = "PLATE_CASH_SALE"
PLATE_CASH_RETURN = "PLATE_CASH_RETURN"
DEFECT = "DEFECT"
ORDER_ROLLBACK = "ORDER_ROLLBACK"


async def get_or_create_stock(db: AsyncSession) -> PlateStock:
    result = await db.execute(select(PlateStock).limit(1))
    stock = result.scalar_one_or_none()
    if stock is None:
        stock = PlateStock(quantity=0)
        db.add(stock)
        await db.flush()
    return stock


async def record_stock_movement(
    db: AsyncSession,
    *,
    movement_type: str,
    quantity_delta: int,
    balance_after: int,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    note: Optional[str] = None,
) -> PlateStockMovement:
    movement = PlateStockMovement(
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        balance_after=balance_after,
        source_type=source_type,
        source_id=source_id,
        note=note,
    )
    db.add(movement)
    await db.flush()
    return movement


def plate_quantity_from_order(order: Order) -> int:
    form_data = order.form_data or {}
    return max(1, int(form_data.get("plate_quantity") or 1))


async def reserved_quantity(db: AsyncSession) -> int:
    result = await db.execute(select(func.coalesce(func.sum(PlateReservation.quantity), 0)))
    return int(result.scalar_one() or 0)


async def reserve_stock_for_order(db: AsyncSession, order: Order, quantity: int) -> None:
    stock = await get_or_create_stock(db)
    reserved_total = await reserved_quantity(db)
    available = stock.quantity - reserved_total
    if available < quantity:
        raise ServiceError(
            f"Недостаточно заготовок на складе. Доступно: {available}, нужно: {quantity}",
            status_code=400,
        )
    db.add(PlateReservation(order_id=order.id, quantity=quantity))
    await db.flush()


async def release_reservation_for_order(db: AsyncSession, order_id: int) -> None:
    await db.execute(delete(PlateReservation).where(PlateReservation.order_id == order_id))
    await db.flush()


async def finalize_stock_for_completed_order(db: AsyncSession, order: Order, quantity: int) -> None:
    stock = await get_or_create_stock(db)
    if stock.quantity < quantity:
        raise ServiceError(
            f"Недостаточно заготовок для завершения заказа. На складе: {stock.quantity}, нужно: {quantity}",
            status_code=400,
        )
    await release_reservation_for_order(db, order.id)
    stock.quantity -= quantity
    db.add(stock)
    await record_stock_movement(
        db,
        movement_type=ORDER_COMPLETED,
        quantity_delta=-quantity,
        balance_after=stock.quantity,
        source_type="order",
        source_id=order.id,
        note=(order.form_data or {}).get("client_fio") or order.public_id,
    )
    await db.flush()


async def build_plate_stock_summary(db: AsyncSession) -> dict:
    stock = await get_or_create_stock(db)
    unissued_statuses = [OrderStatus.PAID, OrderStatus.PLATE_IN_PROGRESS, OrderStatus.PLATE_READY]
    orders_query = select(Order).where(Order.need_plate == True, Order.status.in_(unissued_statuses))
    orders = (await db.execute(orders_query)).scalars().all()

    reserved = sum(plate_quantity_from_order(order) for order in orders)
    reserved_breakdown = [
        {"total_amount": float(order.total_amount), "quantity": plate_quantity_from_order(order)}
        for order in sorted(orders, key=lambda row: row.total_amount, reverse=True)
    ]

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    defects_query = select(func.coalesce(func.sum(PlateDefect.quantity), 0)).where(
        PlateDefect.created_at >= month_start
    )
    defects_month = int((await db.execute(defects_query)).scalar_one() or 0)

    return {
        "quantity": stock.quantity,
        "reserved": reserved,
        "available": max(0, stock.quantity - reserved),
        "reserved_breakdown": reserved_breakdown,
        "defects_this_month": defects_month,
    }


async def add_plate_stock(db: AsyncSession, amount: int) -> dict:
    if amount <= 0:
        raise ServiceError("Количество должно быть больше нуля", status_code=400)
    stock = await get_or_create_stock(db)
    stock.quantity += amount
    db.add(stock)
    await record_stock_movement(
        db,
        movement_type=STOCK_IN,
        quantity_delta=amount,
        balance_after=stock.quantity,
        source_type="warehouse",
        note="Пополнение склада",
    )
    await db.flush()
    return {"quantity": stock.quantity, "added": amount}


async def register_plate_defect(db: AsyncSession) -> dict:
    stock = await get_or_create_stock(db)
    if stock.quantity < 1:
        raise ServiceError("На складе нет заготовок для списания брака", status_code=400)
    stock.quantity -= 1
    db.add(stock)
    db.add(PlateDefect(quantity=1))
    await record_stock_movement(
        db,
        movement_type=DEFECT,
        quantity_delta=-1,
        balance_after=stock.quantity,
        source_type="defect",
        note="Брак",
    )
    await db.flush()
    return {"quantity": stock.quantity, "defect": 1}


async def adjust_stock_for_plate_cash_row(db: AsyncSession, delta: int) -> None:
    if delta == 0:
        return
    stock = await get_or_create_stock(db)
    if delta > 0:
        reserved_total = await reserved_quantity(db)
        available = stock.quantity - reserved_total
        if available < delta:
            raise ServiceError(
                f"Недостаточно заготовок на складе. Доступно: {available}, нужно: {delta}",
                status_code=400,
            )
        stock.quantity -= delta
        movement_type = PLATE_CASH_SALE
        quantity_delta = -delta
    else:
        stock.quantity += abs(delta)
        movement_type = PLATE_CASH_RETURN
        quantity_delta = abs(delta)
    db.add(stock)
    await record_stock_movement(
        db,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        balance_after=stock.quantity,
        source_type="plate_cash_row",
    )
    await db.flush()


def _add_months(month: date, amount: int) -> date:
    month_index = month.month - 1 + amount
    year = month.year + month_index // 12
    month_num = month_index % 12 + 1
    return date(year, month_num, 1)


def _parse_month(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        year, month = value.split("-", 1)
        return date(int(year), int(month), 1)
    except Exception as exc:
        raise ServiceError("Месяц должен быть в формате YYYY-MM", status_code=400) from exc


def _movement_to_dict(row: PlateStockMovement) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "movement_type": row.movement_type,
        "quantity_delta": int(row.quantity_delta or 0),
        "balance_after": int(row.balance_after or 0),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "note": row.note,
    }


async def list_stock_movements(
    db: AsyncSession,
    month_from: Optional[str] = None,
    month_to: Optional[str] = None,
    limit: int = 500,
) -> dict:
    start_month = _parse_month(month_from)
    end_month = _parse_month(month_to)
    query = select(PlateStockMovement).order_by(PlateStockMovement.created_at.desc()).limit(limit)
    if start_month:
        query = query.where(PlateStockMovement.created_at >= datetime.combine(start_month, time.min))
    if end_month:
        query = query.where(PlateStockMovement.created_at < datetime.combine(_add_months(end_month, 1), time.min))
    rows = (await db.execute(query)).scalars().all()
    return {"rows": [_movement_to_dict(row) for row in rows]}


async def build_stock_monthly_summary(
    db: AsyncSession,
    month_from: Optional[str] = None,
    month_to: Optional[str] = None,
) -> dict:
    stock = await get_or_create_stock(db)
    today = datetime.utcnow().date()
    default_to = date(today.year, today.month, 1)
    end_month = _parse_month(month_to) or default_to
    start_month = _parse_month(month_from) or _add_months(end_month, -11)
    if start_month > end_month:
        raise ServiceError("Начальный месяц не может быть позже конечного", status_code=400)

    end_boundary = _add_months(end_month, 1)
    after_end_delta = (
        await db.execute(
            select(func.coalesce(func.sum(PlateStockMovement.quantity_delta), 0)).where(
                PlateStockMovement.created_at >= datetime.combine(end_boundary, time.min)
            )
        )
    ).scalar_one() or 0
    closing_balance = int(stock.quantity - int(after_end_delta))

    rows = []
    cursor = end_month
    while cursor >= start_month:
        next_month = _add_months(cursor, 1)
        movements = (
            await db.execute(
                select(PlateStockMovement).where(
                    PlateStockMovement.created_at >= datetime.combine(cursor, time.min),
                    PlateStockMovement.created_at < datetime.combine(next_month, time.min),
                )
            )
        ).scalars().all()
        month_delta = sum((int(row.quantity_delta or 0) for row in movements), 0)
        opening_balance = closing_balance - month_delta
        incoming = sum((int(row.quantity_delta or 0) for row in movements if row.movement_type == STOCK_IN), 0)
        made_consumed = -sum(
            (
                int(row.quantity_delta or 0)
                for row in movements
                if row.movement_type in {ORDER_COMPLETED, PLATE_CASH_SALE} and int(row.quantity_delta or 0) < 0
            ),
            0,
        )
        returned = sum(
            (
                int(row.quantity_delta or 0)
                for row in movements
                if row.movement_type in {PLATE_CASH_RETURN, ORDER_ROLLBACK} and int(row.quantity_delta or 0) > 0
            ),
            0,
        )
        made = made_consumed - returned
        defects = -sum(
            (int(row.quantity_delta or 0) for row in movements if row.movement_type == DEFECT),
            0,
        )
        rows.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "opening_balance": opening_balance,
                "incoming": incoming,
                "made": made,
                "made_gross": made_consumed,
                "returned": returned,
                "defects": defects,
                "closing_balance": closing_balance,
                "movement_count": len(movements),
            }
        )
        closing_balance = opening_balance
        cursor = _add_months(cursor, -1)

    rows.reverse()
    return {
        "month_from": start_month.strftime("%Y-%m"),
        "month_to": end_month.strftime("%Y-%m"),
        "current_balance": stock.quantity,
        "rows": rows,
    }
