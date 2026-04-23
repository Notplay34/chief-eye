"""Склад заготовок номеров: остатки, пополнение, резерв, списание."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequirePlateAccess, UserInfo
from app.core.database import get_db
from datetime import datetime
from app.models import PlateStock, PlateReservation, PlateDefect, Order, OrderStatus

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("")
async def warehouse_root():
    """Проверка, что модуль склада подключён."""
    return {"status": "ok", "module": "warehouse"}


async def _get_or_create_stock(db: AsyncSession) -> PlateStock:
    r = await db.execute(select(PlateStock).limit(1))
    row = r.scalar_one_or_none()
    if not row:
        row = PlateStock(quantity=0)
        db.add(row)
        await db.flush()
    return row


def _plate_quantity_from_order(order: Order) -> int:
    fd = order.form_data or {}
    return max(1, int(fd.get("plate_quantity") or 1))


@router.get("/plate-stock")
async def get_plate_stock(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Текущий остаток, зарезервировано по невыданным заказам (PAID, PLATE_IN_PROGRESS, PLATE_READY)."""
    stock = await _get_or_create_stock(db)
    # Считаем по фактическим заказам из списка невыданных, а не по таблице резервов (чтобы учитывались и старые заказы без записи)
    unissued_statuses = [OrderStatus.PAID, OrderStatus.PLATE_IN_PROGRESS, OrderStatus.PLATE_READY]
    q_orders = (
        select(Order)
        .where(Order.need_plate == True, Order.status.in_(unissued_statuses))
    )
    orders_result = (await db.execute(q_orders)).scalars().all()
    reserved = sum(_plate_quantity_from_order(o) for o in orders_result)
    reserved_breakdown = [
        {"total_amount": float(o.total_amount), "quantity": _plate_quantity_from_order(o)}
        for o in sorted(orders_result, key=lambda o: o.total_amount, reverse=True)
    ]
    # Браков за текущий месяц
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    q_defects = select(func.coalesce(func.sum(PlateDefect.quantity), 0)).where(
        PlateDefect.created_at >= month_start
    )
    defects_month = int((await db.execute(q_defects)).scalar_one() or 0)
    return {
        "quantity": stock.quantity,
        "reserved": reserved,
        "available": max(0, stock.quantity - reserved),
        "reserved_breakdown": reserved_breakdown,
        "defects_this_month": defects_month,
    }


class AddStockBody(BaseModel):
    amount: int


@router.post("/plate-stock/add")
async def add_plate_stock(
    body: AddStockBody,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Пополнить склад заготовок."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")
    stock = await _get_or_create_stock(db)
    stock.quantity += body.amount
    db.add(stock)
    await db.flush()
    return {"quantity": stock.quantity, "added": body.amount}


@router.post("/plate-stock/defect")
async def add_plate_defect(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Списать 1 шт как брак (вычитается из остатка, учитывается в счётчике за месяц)."""
    stock = await _get_or_create_stock(db)
    if stock.quantity < 1:
        raise HTTPException(status_code=400, detail="На складе нет заготовок для списания брака")
    stock.quantity -= 1
    db.add(stock)
    db.add(PlateDefect(quantity=1))
    await db.flush()
    return {"quantity": stock.quantity, "defect": 1}
