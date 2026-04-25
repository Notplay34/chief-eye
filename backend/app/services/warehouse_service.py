"""Warehouse domain logic for plate stock and reservations."""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderStatus, PlateDefect, PlateReservation, PlateStock
from app.services.errors import ServiceError


async def get_or_create_stock(db: AsyncSession) -> PlateStock:
    result = await db.execute(select(PlateStock).limit(1))
    stock = result.scalar_one_or_none()
    if stock is None:
        stock = PlateStock(quantity=0)
        db.add(stock)
        await db.flush()
    return stock


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
    await db.flush()
    return {"quantity": stock.quantity, "added": amount}


async def register_plate_defect(db: AsyncSession) -> dict:
    stock = await get_or_create_stock(db)
    if stock.quantity < 1:
        raise ServiceError("На складе нет заготовок для списания брака", status_code=400)
    stock.quantity -= 1
    db.add(stock)
    db.add(PlateDefect(quantity=1))
    await db.flush()
    return {"quantity": stock.quantity, "defect": 1}


async def adjust_stock_for_manual_cash_row(db: AsyncSession, delta: int) -> None:
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
    else:
        stock.quantity += abs(delta)
    db.add(stock)
    await db.flush()
