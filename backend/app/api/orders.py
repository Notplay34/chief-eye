from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
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
    PaymentType,
    Employee,
    CashShift,
    ShiftStatus,
    CashRow,
    PlateStock,
    PlateReservation,
    FormHistory,
    PlatePayout,
)
from pydantic import BaseModel

from app.schemas.order import OrderCreate, OrderResponse, OrderDetailResponse
from app.schemas.payment import PayOrderResponse
from app.services.order_service import create_order
from app.services.order_status import can_transition

router = APIRouter(prefix="/orders", tags=["orders"])


async def _get_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    result = await db.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def _current_shift_id(db: AsyncSession, pavilion: int) -> Optional[int]:
    """Текущая открытая смена по павильону (1 или 2). Возвращает id смены или None."""
    q = (
        select(CashShift.id)
        .where(CashShift.pavilion == pavilion, CashShift.status == ShiftStatus.OPEN)
        .order_by(CashShift.opened_at.desc())
        .limit(1)
    )
    r = await db.execute(q)
    return r.scalar_one_or_none()


# Шаблоны для разбивки по графам кассы: заявление, ДКП, номера
_DKP_TEMPLATES = frozenset(("dkp.docx", "dkp_pieces.docx", "dkp_dar.docx"))
_NUMBER_TEMPLATE = "number.docx"


def _order_cash_row_amounts(order: Order):
    """Считает суммы по графам кассы из заказа (form_data.documents + state_duty, income_pavilion2)."""
    fd = order.form_data or {}
    docs = fd.get("documents") or []
    application = Decimal("0")
    dkp = Decimal("0")
    plates = Decimal("0")
    for d in docs:
        t = (d.get("template") or "").strip().lower()
        price = Decimal(str(d.get("price") or 0))
        if t in _DKP_TEMPLATES:
            dkp += price
        elif t == _NUMBER_TEMPLATE:
            plates += price
        else:
            application += price  # заявление и прочие документы
    state_duty = order.state_duty_amount or Decimal("0")
    plates += order.income_pavilion2 or Decimal("0")  # доплата за номера
    total = order.total_amount or Decimal("0")
    return {
        "client_name": (fd.get("client_fio") or fd.get("client_legal_name") or "").strip() or "—",
        "application": application,
        "state_duty": state_duty,
        "dkp": dkp,
        "insurance": Decimal("0"),
        "plates": plates,
        "total": total,
    }


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
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not can_transition(order.status, OrderStatus.PAID):
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя принять оплату для заказа со статусом {order.status.value}",
        )
    emp_id = employee_id if employee_id is not None else user.id
    shift_1 = await _current_shift_id(db, 1)
    shift_2 = await _current_shift_id(db, 2)
    if order.state_duty_amount > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.state_duty_amount,
                type=PaymentType.STATE_DUTY,
                employee_id=emp_id,
                shift_id=shift_1,
            )
        )
    if order.income_pavilion1 > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.income_pavilion1,
                type=PaymentType.INCOME_PAVILION1,
                employee_id=emp_id,
                shift_id=shift_1,
            )
        )
    if order.income_pavilion2 > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.income_pavilion2,
                type=PaymentType.INCOME_PAVILION2,
                employee_id=emp_id,
                shift_id=shift_2,
            )
        )
    order.status = OrderStatus.PAID
    db.add(order)
    await db.flush()
    # Строка в кассу: ФИО и суммы по графам (заявление, госпошлина, ДКП, страховка, номера, итого)
    amounts = _order_cash_row_amounts(order)
    db.add(
        CashRow(
            client_name=amounts["client_name"],
            application=amounts["application"],
            state_duty=amounts["state_duty"],
            dkp=amounts["dkp"],
            insurance=amounts["insurance"],
            plates=amounts["plates"],
            total=amounts["total"],
        )
    )
    await db.flush()
    # Запись в историю заполнения формы (для подстановки по клику на странице формы)
    db.add(FormHistory(order_id=order.id, form_data=order.form_data))
    await db.flush()
    logger.info("Оплата принята по заказу id=%s, строка кассы добавлена", order.id)
    return PayOrderResponse(
        order_id=order.id,
        public_id=order.public_id,
        status=OrderStatus.PAID.value,
    )


def _plate_amount_from_order(order: Order) -> Decimal:
    """Сумма только по номерам: number.docx из form_data + доплаты (INCOME_PAVILION2) не хранятся в заказе, считаются по платежам."""
    fd = order.form_data or {}
    docs = fd.get("documents") or []
    total = Decimal("0")
    for d in docs:
        t = (d.get("template") or "").strip().lower()
        if t == _NUMBER_TEMPLATE:
            total += Decimal(str(d.get("price") or 0))
    return total


@router.get("/plate-list")
async def list_orders_for_plate(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Список заказов с номерами для павильона 2: клиент, сумма (только номера), оплачено, долг."""
    from sqlalchemy import func

    q = (
        select(Order, func.coalesce(func.sum(Payment.amount), 0).label("total_paid"))
        .outerjoin(Payment, Payment.order_id == Order.id)
        .where(Order.need_plate == True)
        .where(Order.status.in_([OrderStatus.PAID, OrderStatus.PLATE_IN_PROGRESS, OrderStatus.PLATE_READY]))
        .group_by(Order.id)
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    result = await db.execute(q)
    rows = result.all()
    # Доплаты за номера (INCOME_PAVILION2) по заказам
    order_ids = [order.id for order, _ in rows]
    pay_extra_sums = {}
    if order_ids:
        from sqlalchemy import and_
        q2 = (
            select(Payment.order_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(and_(Payment.order_id.in_(order_ids), Payment.type == PaymentType.INCOME_PAVILION2))
            .group_by(Payment.order_id)
        )
        r2 = await db.execute(q2)
        for oid, s in r2.all():
            pay_extra_sums[oid] = float(s or 0)
    out = []
    for order, total_paid in rows:
        total_paid = float(total_paid or 0)
        fd = order.form_data or {}
        client = fd.get("client_fio") or fd.get("client_legal_name") or "—"
        brand_model = fd.get("brand_model") or ""
        plate_only = _plate_amount_from_order(order) + Decimal(str(pay_extra_sums.get(order.id, 0)))
        out.append({
            "id": order.id,
            "public_id": order.public_id,
            "status": order.status.value,
            "total_amount": float(order.total_amount),
            "plate_amount": float(plate_only),
            "income_pavilion2": float(order.income_pavilion2),
            "client": client,
            "brand_model": brand_model,
            "total_paid": total_paid,
            "debt": float(order.total_amount) - total_paid,
            "created_at": order.created_at.isoformat() if order.created_at else "",
        })
    return out


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
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
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
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
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
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    r = await db.execute(select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at))
    payments = r.scalars().all()
    total_paid = sum(float(p.amount) for p in payments)
    return {
        "payments": [{"amount": float(p.amount), "type": p.type.value, "created_at": p.created_at.isoformat() if p.created_at else ""} for p in payments],
        "total_paid": total_paid,
        "debt": float(order.total_amount) - total_paid,
    }


@router.post("/{order_id}/pay-extra")
async def pay_extra(
    order_id: int,
    body: PayExtraBody,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Доплата за номера (INCOME_PAVILION2)."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше нуля")
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not order.need_plate:
        raise HTTPException(status_code=400, detail="У заказа нет номера для доплаты")
    shift_2 = await _current_shift_id(db, 2)
    db.add(
        Payment(
            order_id=order.id,
            amount=body.amount,
            type=PaymentType.INCOME_PAVILION2,
            employee_id=_user.id,
            shift_id=shift_2,
        )
    )
    # Строка в кассу: доплата за номера (ФИО из заказа, номера и итого = сумма доплаты)
    fd = order.form_data or {}
    client_name = (fd.get("client_fio") or fd.get("client_legal_name") or "").strip() or "—"
    db.add(
        CashRow(
            client_name=client_name,
            application=Decimal("0"),
            state_duty=Decimal("0"),
            dkp=Decimal("0"),
            insurance=Decimal("0"),
            plates=Decimal(str(body.amount)),
            total=Decimal(str(body.amount)),
        )
    )
    await db.flush()
    logger.info("Доплата за номера id=%s сумма=%s, строка кассы добавлена", order.id, body.amount)
    return {"order_id": order.id, "amount": body.amount, "type": "INCOME_PAVILION2"}


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


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    new_status = body.status
    order = await _get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not can_transition(order.status, new_status):
        raise HTTPException(
            status_code=400,
            detail=f"Переход из {order.status.value} в {new_status.value} невозможен",
        )
    qty = _plate_quantity_from_order(order) if order.need_plate else 0

    # Резерв при переходе в изготовление
    if order.status == OrderStatus.PAID and new_status == OrderStatus.PLATE_IN_PROGRESS and qty > 0:
        stock = await _get_or_create_stock(db)
        res_sum = (await db.execute(
            select(func.coalesce(func.sum(PlateReservation.quantity), 0))
        )).scalar_one() or 0
        available = stock.quantity - int(res_sum)
        if available < qty:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно заготовок на складе. Доступно: {available}, нужно: {qty}",
            )
        db.add(PlateReservation(order_id=order.id, quantity=qty))
        await db.flush()

    # Списание и снятие резерва при завершении
    if new_status == OrderStatus.COMPLETED and qty > 0:
        await db.execute(delete(PlateReservation).where(PlateReservation.order_id == order.id))
        stock = await _get_or_create_stock(db)
        stock.quantity -= qty
        db.add(stock)
        await db.flush()
        logger.info("Списание со склада: заказ %s, кол-во %s", order.id, qty)

    # Снятие резерва при проблеме
    if new_status == OrderStatus.PROBLEM and order.need_plate and qty > 0:
        await db.execute(delete(PlateReservation).where(PlateReservation.order_id == order.id))
        await db.flush()

    # При завершении заказа с номерами — добавляем запись в реестр выдачи денег за номера
    if new_status == OrderStatus.COMPLETED and order.need_plate:
        # Проверяем, не создана ли уже запись
        existing = await db.execute(select(PlatePayout).where(PlatePayout.order_id == order.id))
        if existing.scalar_one_or_none() is None:
            # Сумма по номерам: цена номеров из формы + все платежи INCOME_PAVILION2
            base_amount = _plate_amount_from_order(order)
            extra_sum = (
                await db.execute(
                    select(func.coalesce(func.sum(Payment.amount), 0)).where(
                        Payment.order_id == order.id,
                        Payment.type == PaymentType.INCOME_PAVILION2,
                    )
                )
            ).scalar_one() or Decimal("0")
            plate_amount = base_amount + extra_sum
            if plate_amount > 0:
                fd = order.form_data or {}
                client_name = (fd.get("client_fio") or fd.get("client_legal_name") or "").strip() or "—"
                db.add(
                    PlatePayout(
                        order_id=order.id,
                        client_name=client_name,
                        amount=plate_amount,
                    )
                )
                await db.flush()

    order.status = new_status
    db.add(order)
    return {"order_id": order.id, "public_id": order.public_id, "status": new_status.value}
