from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentItem(BaseModel):
    """Элемент прейскуранта: документ для печати и его цена."""
    template: str
    price: Decimal = Field(..., ge=0)
    label: Optional[str] = None


class OrderCreate(BaseModel):
    """Данные формы оператора (раздел 13 PROJECT_CONTEXT)."""
    client_fio: Optional[str] = None
    client_passport: Optional[str] = None
    client_address: Optional[str] = None
    client_phone: Optional[str] = None
    client_comment: Optional[str] = None
    client_is_legal: bool = False
    client_legal_name: Optional[str] = None
    client_inn: Optional[str] = None
    client_ogrn: Optional[str] = None
    seller_fio: Optional[str] = None
    seller_passport: Optional[str] = None
    seller_address: Optional[str] = None
    trustee_fio: Optional[str] = None
    trustee_passport: Optional[str] = None
    trustee_basis: Optional[str] = None
    vin: Optional[str] = None
    brand_model: Optional[str] = None
    vehicle_type: Optional[str] = None
    year: Optional[str] = None
    engine: Optional[str] = None
    chassis: Optional[str] = None
    body: Optional[str] = None
    color: Optional[str] = None
    srts: Optional[str] = None
    plate_number: Optional[str] = None
    pts: Optional[str] = None
    dkp_date: Optional[str] = None
    dkp_number: Optional[str] = None
    dkp_summary: Optional[str] = None
    service_type: Optional[str] = None
    need_plate: bool = False
    plate_quantity: int = Field(default=1, ge=1, le=10, description="Количество номеров для изготовления")
    state_duty: Decimal = Field(default=Decimal("0"), ge=0)
    extra_amount: Decimal = Field(default=Decimal("0"), ge=0)
    plate_amount: Decimal = Field(default=Decimal("0"), ge=0)
    summa_dkp: Decimal = Field(default=Decimal("0"), ge=0)
    employee_id: Optional[int] = None
    # Список документов для печати (прейскурант): сумма по ним считается автоматически
    documents: Optional[List[DocumentItem]] = None


class OrderResponse(BaseModel):
    id: int
    public_id: str
    status: str
    total_amount: Decimal
    state_duty_amount: Decimal
    income_pavilion1: Decimal
    income_pavilion2: Decimal
    need_plate: bool
    service_type: Optional[str] = None
    created_at: str
    client: Optional[str] = None  # для списка: из form_data

    class Config:
        from_attributes = True


class OrderDetailResponse(OrderResponse):
    """Заказ с деталями для админки: form_data и кто оформил."""
    form_data: Optional[dict] = None
    created_by_name: Optional[str] = None
