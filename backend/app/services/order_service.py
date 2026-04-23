from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.price_list import get_label_by_template
from app.models import Order, OrderStatus
from app.schemas.order import OrderCreate


def _form_data_from_create(d: OrderCreate) -> dict:
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
    if d.documents:
        out["documents"] = [
            {"template": x.template, "label": x.label or get_label_by_template(x.template), "price": str(x.price)}
            for x in d.documents
        ]
    return out


async def create_order(db: AsyncSession, data: OrderCreate) -> Order:
    state_duty = data.state_duty
    if data.documents:
        income_p1 = sum(doc.price for doc in data.documents)
        need_plate = any(doc.template == "number.docx" for doc in data.documents)
        service_type = data.documents[0].template if data.documents else data.service_type
    else:
        income_p1 = data.extra_amount + (data.plate_amount if data.need_plate else Decimal("0"))
        need_plate = data.need_plate
        service_type = data.service_type
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
        form_data=_form_data_from_create(data),
        employee_id=data.employee_id,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order
