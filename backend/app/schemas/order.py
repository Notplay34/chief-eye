from decimal import Decimal
from typing import Optional, List
import re

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.services.order_validation import validate_dkp_date


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
    # Список документов для печати (прейскурант): сумма по ним считается автоматически
    documents: Optional[List[DocumentItem]] = None

    @field_validator(
        "client_fio",
        "client_passport",
        "client_address",
        "client_phone",
        "client_comment",
        "client_legal_name",
        "client_inn",
        "client_ogrn",
        "seller_fio",
        "seller_passport",
        "seller_address",
        "trustee_fio",
        "trustee_passport",
        "trustee_basis",
        "vin",
        "brand_model",
        "vehicle_type",
        "year",
        "engine",
        "chassis",
        "body",
        "color",
        "srts",
        "plate_number",
        "pts",
        "dkp_date",
        "dkp_number",
        "dkp_summary",
        "service_type",
        mode="before",
    )
    @classmethod
    def _normalize_optional_strings(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        return cleaned or None

    @field_validator("client_phone")
    @classmethod
    def _validate_client_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 11 or not digits.startswith("7"):
            raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX")
        return "+" + digits

    @field_validator("vin")
    @classmethod
    def _validate_vin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        vin = value.upper()
        if len(vin) != 17 or any(ch in vin for ch in "IOQ"):
            raise ValueError("VIN должен содержать 17 символов без I, O и Q")
        return vin

    @field_validator("client_inn")
    @classmethod
    def _validate_inn(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) not in (10, 12):
            raise ValueError("ИНН должен содержать 10 или 12 цифр")
        return digits

    @field_validator("client_ogrn")
    @classmethod
    def _validate_ogrn(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 13:
            raise ValueError("ОГРН должен содержать 13 цифр")
        return digits

    @field_validator("year")
    @classmethod
    def _validate_year(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("Год выпуска должен содержать 4 цифры")
        year = int(value)
        if year < 1900 or year > 2100:
            raise ValueError("Год выпуска вне допустимого диапазона")
        return value

    @field_validator("plate_number")
    @classmethod
    def _validate_plate_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", "", value.upper())
        if len(normalized) < 6 or len(normalized) > 10:
            raise ValueError("Госномер должен содержать от 6 до 10 символов")
        return normalized

    @field_validator("client_passport", "seller_passport", "trustee_passport")
    @classmethod
    def _validate_passport(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            raise ValueError("Паспорт должен содержать 10 цифр")
        return f"{digits[:4]} {digits[4:]}"

    @field_validator("srts", "pts")
    @classmethod
    def _validate_vehicle_docs(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", "", value.upper())
        if len(normalized) < 6 or len(normalized) > 12:
            raise ValueError("Номер документа должен содержать от 6 до 12 символов")
        return normalized

    @field_validator("dkp_date")
    @classmethod
    def _validate_dkp_date(cls, value: Optional[str]) -> Optional[str]:
        return validate_dkp_date(value)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

class OrderDetailResponse(OrderResponse):
    """Заказ с деталями для админки: form_data и кто оформил."""
    form_data: Optional[dict] = None
    created_by_name: Optional[str] = None


class PlateOrderResponse(BaseModel):
    id: int
    public_id: str
    status: str
    client: Optional[str] = None
    brand_model: Optional[str] = None
    plate_amount: Decimal
    debt: Decimal
    plate_document: str = "zaiavlenie_na_nomera.docx"
    created_at: str
