from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.price_list import get_label_by_template
from app.models import CashRow, DocumentPrice, FormHistory, Order, OrderStatus, Payment, PaymentType, PlatePayout
from app.schemas.order import OrderCreate
from app.schemas.payment import PayOrderResponse
from app.services.cash_service import get_current_shift
from app.services.errors import ServiceError
from app.services.order_status import can_transition
from app.services.template_registry import is_sellable_template, supported_sellable_templates
from app.services.warehouse_service import (
    finalize_stock_for_completed_order,
    plate_quantity_from_order,
    release_reservation_for_order,
    reserve_stock_for_order,
)

_DKP_TEMPLATES = frozenset(("dkp.docx", "dkp_pieces.docx", "dkp_dar.docx"))
_NUMBER_TEMPLATE = "number.docx"


def _form_data_from_create(d: OrderCreate, canonical_documents: list[dict]) -> dict:
    out = {
        "client_fio": d.client_fio,
        "client_passport": d.client_passport,
        "client_address": d.client_address,
        "client_phone": d.client_phone,
        "client_comment": d.client_comment,
        "client_is_legal": d.client_is_legal,
        "client_legal_name": d.client_legal_name,
        "client_inn": d.client_inn,
        "client_ogrn": d.client_ogrn,
        "seller_fio": d.seller_fio,
        "seller_passport": d.seller_passport,
        "seller_address": d.seller_address,
        "trustee_fio": d.trustee_fio,
        "trustee_passport": d.trustee_passport,
        "trustee_basis": d.trustee_basis,
        "vin": d.vin,
        "brand_model": d.brand_model,
        "vehicle_type": d.vehicle_type,
        "year": d.year,
        "engine": d.engine,
        "chassis": d.chassis,
        "body": d.body,
        "color": d.color,
        "srts": d.srts,
        "plate_number": d.plate_number,
        "pts": d.pts,
        "dkp_date": d.dkp_date,
        "dkp_number": d.dkp_number,
        "dkp_summary": d.dkp_summary,
        "summa_dkp": str(d.summa_dkp),
        "plate_quantity": d.plate_quantity,
    }
    if canonical_documents:
        out["documents"] = canonical_documents
    return out


async def _load_canonical_documents(db: AsyncSession, documents: list) -> list[dict]:
    if not documents:
        raise ServiceError("Заказ должен содержать хотя бы один документ", status_code=400)

    templates = [document.template for document in documents]
    unsupported = [template for template in templates if not is_sellable_template(template)]
    supported_now = supported_sellable_templates()
    unavailable = [template for template in templates if template not in supported_now]
    if unsupported:
        raise ServiceError(f"Недопустимые документы: {', '.join(sorted(set(unsupported)))}", status_code=400)
    if unavailable:
        raise ServiceError(f"Документы недоступны для печати: {', '.join(sorted(set(unavailable)))}", status_code=400)

    result = await db.execute(select(DocumentPrice).where(DocumentPrice.template.in_(templates)))
    price_rows = {row.template: row for row in result.scalars().all()}
    missing = [template for template in templates if template not in price_rows]
    if missing:
        raise ServiceError(f"Документы отсутствуют в прайсе: {', '.join(sorted(set(missing)))}", status_code=400)

    canonical_documents: list[dict] = []
    for document in documents:
        price_row = price_rows[document.template]
        canonical_documents.append(
            {
                "template": price_row.template,
                "label": price_row.label or get_label_by_template(price_row.template),
                "price": str(price_row.price),
            }
        )
    return canonical_documents


def _validate_order_business_rules(data: OrderCreate, canonical_documents: list[dict]) -> None:
    if not canonical_documents:
        raise ServiceError("Заказ должен содержать хотя бы один документ", status_code=400)

    templates = [document["template"] for document in canonical_documents]
    has_plate_document = _NUMBER_TEMPLATE in templates
    if data.need_plate and not has_plate_document:
        raise ServiceError("Для заказа с номерами нужно добавить услугу изготовления номера", status_code=400)
    if not data.need_plate and has_plate_document:
        raise ServiceError("Документ изготовления номера требует включить режим заказа с номерами", status_code=400)

    docs_total = sum((Decimal(str(document["price"])) for document in canonical_documents), Decimal("0"))
    total = docs_total + data.state_duty
    if total <= 0:
        raise ServiceError("Пустой заказ создавать нельзя", status_code=400)


async def create_order(db: AsyncSession, data: OrderCreate, employee_id: int) -> Order:
    canonical_documents = await _load_canonical_documents(db, data.documents or [])
    _validate_order_business_rules(data, canonical_documents)

    state_duty = data.state_duty
    income_p1 = sum((Decimal(str(document["price"])) for document in canonical_documents), Decimal("0"))
    need_plate = any(document["template"] == "number.docx" for document in canonical_documents)
    service_type = canonical_documents[0]["template"]
    income_p2 = Decimal("0")
    total = state_duty + income_p1 + income_p2

    order = Order(
        status=OrderStatus.AWAITING_PAYMENT,
        total_amount=total,
        state_duty_amount=state_duty,
        income_pavilion1=income_p1,
        income_pavilion2=income_p2,
        need_plate=need_plate,
        service_type=service_type,
        form_data=_form_data_from_create(data, canonical_documents),
        employee_id=employee_id,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


async def get_order_or_error(db: AsyncSession, order_id: int) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise ServiceError("Заказ не найден", status_code=404)
    return order


def plate_amount_from_order(order: Order) -> Decimal:
    form_data = order.form_data or {}
    docs = form_data.get("documents") or []
    total = Decimal("0")
    for doc in docs:
        template = (doc.get("template") or "").strip().lower()
        if template == _NUMBER_TEMPLATE:
            total += Decimal(str(doc.get("price") or 0))
    return total


def order_cash_row_amounts(order: Order) -> dict:
    form_data = order.form_data or {}
    docs = form_data.get("documents") or []
    application = Decimal("0")
    dkp = Decimal("0")
    plates = Decimal("0")
    for doc in docs:
        template = (doc.get("template") or "").strip().lower()
        price = Decimal(str(doc.get("price") or 0))
        if template in _DKP_TEMPLATES:
            dkp += price
        elif template == _NUMBER_TEMPLATE:
            plates += price
        else:
            application += price
    state_duty = order.state_duty_amount or Decimal("0")
    plates += order.income_pavilion2 or Decimal("0")
    total = order.total_amount or Decimal("0")
    return {
        "client_name": (form_data.get("client_fio") or form_data.get("client_legal_name") or "").strip() or "—",
        "application": application,
        "state_duty": state_duty,
        "dkp": dkp,
        "insurance": Decimal("0"),
        "plates": plates,
        "total": total,
    }


async def accept_order_payment(db: AsyncSession, order: Order, employee_id: int) -> PayOrderResponse:
    if not can_transition(order.status, OrderStatus.PAID):
        raise ServiceError(
            f"Нельзя принять оплату для заказа со статусом {order.status.value}",
            status_code=400,
        )

    shift_1 = await get_current_shift(db, 1)
    shift_2 = await get_current_shift(db, 2)
    if order.state_duty_amount > 0 or order.income_pavilion1 > 0:
        if shift_1 is None:
            raise ServiceError("Для приёма оплаты по павильону 1 откройте смену", status_code=400)
    if order.income_pavilion2 > 0:
        if shift_2 is None:
            raise ServiceError("Для платежей павильона 2 откройте смену", status_code=400)
    if order.state_duty_amount > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.state_duty_amount,
                type=PaymentType.STATE_DUTY,
                employee_id=employee_id,
                shift_id=shift_1.id,
            )
        )
    if order.income_pavilion1 > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.income_pavilion1,
                type=PaymentType.INCOME_PAVILION1,
                employee_id=employee_id,
                shift_id=shift_1.id,
            )
        )
    if order.income_pavilion2 > 0:
        db.add(
            Payment(
                order_id=order.id,
                amount=order.income_pavilion2,
                type=PaymentType.INCOME_PAVILION2,
                employee_id=employee_id,
                shift_id=shift_2.id,
            )
        )

    order.status = OrderStatus.PAID
    db.add(order)
    await db.flush()

    amounts = order_cash_row_amounts(order)
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
    db.add(FormHistory(order_id=order.id, form_data=order.form_data))
    await db.flush()
    return PayOrderResponse(order_id=order.id, public_id=order.public_id, status=OrderStatus.PAID.value)


async def get_order_payments_summary(db: AsyncSession, order: Order) -> dict:
    result = await db.execute(select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at))
    payments = result.scalars().all()
    total_paid = sum(float(payment.amount) for payment in payments)
    return {
        "payments": [
            {
                "amount": float(payment.amount),
                "type": payment.type.value,
                "created_at": payment.created_at.isoformat() if payment.created_at else "",
            }
            for payment in payments
        ],
        "total_paid": total_paid,
        "debt": float(order.total_amount) - total_paid,
    }


async def record_plate_extra_payment(db: AsyncSession, order: Order, amount: Decimal, employee_id: int) -> dict:
    if amount <= 0:
        raise ServiceError("Сумма должна быть больше нуля", status_code=400)
    if not order.need_plate:
        raise ServiceError("У заказа нет номера для доплаты", status_code=400)

    shift_2 = await get_current_shift(db, 2)
    if shift_2 is None:
        raise ServiceError("Для доплаты за номера откройте смену павильона 2", status_code=400)
    db.add(
        Payment(
            order_id=order.id,
            amount=amount,
            type=PaymentType.INCOME_PAVILION2,
            employee_id=employee_id,
            shift_id=shift_2.id,
        )
    )
    form_data = order.form_data or {}
    client_name = (form_data.get("client_fio") or form_data.get("client_legal_name") or "").strip() or "—"
    db.add(
        CashRow(
            client_name=client_name,
            application=Decimal("0"),
            state_duty=Decimal("0"),
            dkp=Decimal("0"),
            insurance=Decimal("0"),
            plates=amount,
            total=amount,
        )
    )
    await db.flush()
    return {"order_id": order.id, "amount": float(amount), "type": "INCOME_PAVILION2"}


async def build_plate_list(db: AsyncSession, limit: int = 100) -> list[dict]:
    query = (
        select(Order, func.coalesce(func.sum(Payment.amount), 0).label("total_paid"))
        .outerjoin(Payment, Payment.order_id == Order.id)
        .where(Order.need_plate == True)
        .where(Order.status.in_([OrderStatus.PAID, OrderStatus.PLATE_IN_PROGRESS, OrderStatus.PLATE_READY]))
        .group_by(Order.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(query)).all()

    order_ids = [order.id for order, _ in rows]
    extra_by_order: dict[int, float] = {}
    if order_ids:
        extra_query = (
            select(Payment.order_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.order_id.in_(order_ids), Payment.type == PaymentType.INCOME_PAVILION2)
            .group_by(Payment.order_id)
        )
        for order_id, total in (await db.execute(extra_query)).all():
            extra_by_order[order_id] = float(total or 0)

    output = []
    for order, total_paid in rows:
        form_data = order.form_data or {}
        client = form_data.get("client_fio") or form_data.get("client_legal_name") or "—"
        plate_total = plate_amount_from_order(order) + Decimal(str(extra_by_order.get(order.id, 0)))
        total_paid_float = float(total_paid or 0)
        output.append(
            {
                "id": order.id,
                "public_id": order.public_id,
                "status": order.status.value,
                "total_amount": float(order.total_amount),
                "plate_amount": float(plate_total),
                "income_pavilion2": float(order.income_pavilion2),
                "client": client,
                "brand_model": form_data.get("brand_model") or "",
                "total_paid": total_paid_float,
                "debt": float(order.total_amount) - total_paid_float,
                "created_at": order.created_at.isoformat() if order.created_at else "",
            }
        )
    return output


async def _ensure_plate_payout_for_completed_order(db: AsyncSession, order: Order) -> None:
    existing = await db.execute(select(PlatePayout).where(PlatePayout.order_id == order.id))
    if existing.scalar_one_or_none() is not None:
        return

    base_amount = plate_amount_from_order(order)
    extra_sum = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.order_id == order.id,
                Payment.type == PaymentType.INCOME_PAVILION2,
            )
        )
    ).scalar_one() or Decimal("0")
    plate_amount = base_amount + extra_sum
    if plate_amount <= 0:
        return

    form_data = order.form_data or {}
    client_name = (form_data.get("client_fio") or form_data.get("client_legal_name") or "").strip() or "—"
    db.add(PlatePayout(order_id=order.id, client_name=client_name, amount=plate_amount))
    await db.flush()


async def update_order_status(db: AsyncSession, order: Order, new_status: OrderStatus) -> dict:
    if not can_transition(order.status, new_status):
        raise ServiceError(
            f"Переход из {order.status.value} в {new_status.value} невозможен",
            status_code=400,
        )

    quantity = plate_quantity_from_order(order) if order.need_plate else 0

    if order.status == OrderStatus.PAID and new_status == OrderStatus.PLATE_IN_PROGRESS and quantity > 0:
        await reserve_stock_for_order(db, order, quantity)

    if new_status == OrderStatus.COMPLETED and quantity > 0:
        await finalize_stock_for_completed_order(db, order, quantity)

    if new_status == OrderStatus.PROBLEM and order.need_plate and quantity > 0:
        await release_reservation_for_order(db, order.id)

    if new_status == OrderStatus.COMPLETED and order.need_plate:
        await _ensure_plate_payout_for_completed_order(db, order)

    order.status = new_status
    db.add(order)
    await db.flush()
    return {"order_id": order.id, "public_id": order.public_id, "status": new_status.value}
