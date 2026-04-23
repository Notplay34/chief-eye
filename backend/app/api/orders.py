from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.permissions import can_access_pavilion
from app.api.auth import RequireFormAccess, RequireAnalyticsAccess, RequireOrdersListAccess, RequirePlateAccess, UserInfo

logger = get_logger(__name__)
from app.models import (
    Order,
    OrderStatus,
    Payment,
    Employee,
)
from pydantic import BaseModel

from app.schemas.order import OrderCreate, OrderResponse, OrderDetailResponse
from app.schemas.payment import PayOrderResponse
from app.services.errors import ServiceError
from app.services.order_service import (
    accept_order_payment,
    build_plate_list,
    create_order,
    get_order_or_error,
    get_order_payments_summary,
    record_plate_extra_payment,
    update_order_status as update_order_status_service,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("", response_model=OrderResponse)
async def post_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireFormAccess),
):
    order = await create_order(db, data)
    logger.info("Создан заказ id=%s public_id=%s", order.id, order.public_id)
    return OrderResponse(
        id=order.id,
        public_id=order.public_id,
        status=order.status.value,
        total_amount=order.total_amount,
        state_duty_amount=order.state_duty_amount,
        income_pavilion1=order.income_pavilion1,
        income_pavilion2=order.income_pavilion2,
        need_plate=order.need_plate,
        service_type=order.service_type,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


@router.post("/{order_id}/pay", response_model=PayOrderResponse)
async def pay_order(
    order_id: int,
    employee_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireFormAccess),
):
    emp_id = employee_id if employee_id is not None else user.id
    try:
        order = await get_order_or_error(db, order_id)
        response = await accept_order_payment(db, order, emp_id)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Оплата принята по заказу id=%s, строка кассы добавлена", order.id)
    return response


@router.get("/plate-list")
async def list_orders_for_plate(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Список заказов с номерами для павильона 2: клиент, сумма (только номера), оплачено, долг."""
    return await build_plate_list(db)


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = None,
    need_plate: Optional[bool] = None,
    pavilion: Optional[int] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireOrdersListAccess),
):
    """Список заказов. pavilion=1 — заявки павильона 1 (форма), pavilion=2 — только с номерами (need_plate)."""
    if pavilion is not None:
        if pavilion not in (1, 2):
            raise HTTPException(status_code=400, detail="Павильон должен быть 1 или 2")
        if not can_access_pavilion(user.role, pavilion):
            raise HTTPException(status_code=403, detail="Нет доступа к этому павильону")
        if pavilion == 2:
            need_plate = True
    q = select(Order).order_by(Order.created_at.desc()).limit(limit)
    if status is not None:
        q = q.where(Order.status == status)
    if need_plate is not None:
        q = q.where(Order.need_plate == need_plate)
    result = await db.execute(q)
    orders = result.scalars().all()
    out = []
    for o in orders:
        client = None
        if o.form_data:
            client = (o.form_data.get("client_fio") or o.form_data.get("client_legal_name") or "").strip() or None
        out.append(OrderResponse(
            id=o.id,
            public_id=o.public_id,
            status=o.status.value,
            total_amount=o.total_amount,
            state_duty_amount=o.state_duty_amount,
            income_pavilion1=o.income_pavilion1,
            income_pavilion2=o.income_pavilion2,
            need_plate=o.need_plate,
            service_type=o.service_type,
            created_at=o.created_at.isoformat() if o.created_at else "",
            client=client,
        ))
    return out


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireOrdersListAccess),
):
    try:
        order = await get_order_or_error(db, order_id)
    except ServiceError as exc:
        _raise_service_error(exc)
    return OrderResponse(
        id=order.id,
        public_id=order.public_id,
        status=order.status.value,
        total_amount=order.total_amount,
        state_duty_amount=order.state_duty_amount,
        income_pavilion1=order.income_pavilion1,
        income_pavilion2=order.income_pavilion2,
        need_plate=order.need_plate,
        service_type=order.service_type,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


@router.get("/{order_id}/detail", response_model=OrderDetailResponse)
async def get_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    """Детали заказа для админки: form_data и кто оформил."""
    try:
        order = await get_order_or_error(db, order_id)
    except ServiceError as exc:
        _raise_service_error(exc)
    created_by_name = None
    if order.employee_id:
        r = await db.execute(select(Employee.name).where(Employee.id == order.employee_id))
        created_by_name = r.scalar_one_or_none()
    return OrderDetailResponse(
        id=order.id,
        public_id=order.public_id,
        status=order.status.value,
        total_amount=order.total_amount,
        state_duty_amount=order.state_duty_amount,
        income_pavilion1=order.income_pavilion1,
        income_pavilion2=order.income_pavilion2,
        need_plate=order.need_plate,
        service_type=order.service_type,
        created_at=order.created_at.isoformat() if order.created_at else "",
        form_data=order.form_data,
        created_by_name=created_by_name,
    )


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class PayExtraBody(BaseModel):
    amount: float


@router.get("/{order_id}/payments")
async def get_order_payments(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireOrdersListAccess),
):
    """Список платежей по заказу (для расчёта total_paid и долга)."""
    try:
        order = await get_order_or_error(db, order_id)
        return await get_order_payments_summary(db, order)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.post("/{order_id}/pay-extra")
async def pay_extra(
    order_id: int,
    body: PayExtraBody,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Доплата за номера (INCOME_PAVILION2)."""
    try:
        order = await get_order_or_error(db, order_id)
        result = await record_plate_extra_payment(db, order, Decimal(str(body.amount)), _user.id)
    except ServiceError as exc:
        _raise_service_error(exc)
    logger.info("Доплата за номера id=%s сумма=%s, строка кассы добавлена", order.id, body.amount)
    return result


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    new_status = body.status
    try:
        order = await get_order_or_error(db, order_id)
        return await update_order_status_service(db, order, new_status)
    except ServiceError as exc:
        _raise_service_error(exc)
