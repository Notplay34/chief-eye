from decimal import Decimal
from typing import Optional, List
import re
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from app.services.order_validation import validate_dkp_date


class DocumentItem(BaseModel):
    """Элемент прейскуранта: документ для печати и его цена."""
    template: str
    price: Decimal = Field(..., ge=0)
    label: Optional[str] = None


class OrderCreate(BaseModel):
    """Данные формы оператора (раздел 13 PROJECT_CONTEXT)."""
    client_fio: Optional[str] = None
    client_birth_date: Optional[str] = None
    client_birth_place: Optional[str] = None
    client_passport: Optional[str] = None
    client_passport_series: Optional[str] = None
    client_passport_number: Optional[str] = None
    client_passport_issued_by: Optional[str] = None
    client_passport_issued_date: Optional[str] = None
    client_passport_division_code: Optional[str] = None
    client_address: Optional[str] = None
    client_phone: Optional[str] = None
    client_comment: Optional[str] = None
    client_is_legal: bool = False
    client_legal_name: Optional[str] = None
    client_inn: Optional[str] = None
    client_ogrn: Optional[str] = None
    seller_fio: Optional[str] = None
    seller_birth_date: Optional[str] = None
    seller_passport: Optional[str] = None
    seller_passport_series: Optional[str] = None
    seller_passport_number: Optional[str] = None
    seller_passport_issued_by: Optional[str] = None
    seller_passport_issued_date: Optional[str] = None
    seller_passport_division_code: Optional[str] = None
    seller_address: Optional[str] = None
    trustee_fio: Optional[str] = None
    trustee_birth_date: Optional[str] = None
    trustee_passport: Optional[str] = None
    trustee_passport_series: Optional[str] = None
    trustee_passport_number: Optional[str] = None
    trustee_passport_issued_by: Optional[str] = None
    trustee_passport_issued_date: Optional[str] = None
    trustee_passport_division_code: Optional[str] = None
    trustee_basis: Optional[str] = None
    vin: Optional[str] = None
    brand_model: Optional[str] = None
    vehicle_type: Optional[str] = None
    year: Optional[str] = None
    engine: Optional[str] = None
    chassis: Optional[str] = None
    power: Optional[str] = None
    mass: Optional[str] = None
    body: Optional[str] = None
    color: Optional[str] = None
    srts: Optional[str] = None
    srts_series: Optional[str] = None
    srts_number: Optional[str] = None
    srts_issued_by: Optional[str] = None
    srts_issued_date: Optional[str] = None
    plate_number: Optional[str] = None
    pts: Optional[str] = None
    pts_series: Optional[str] = None
    pts_number: Optional[str] = None
    pts_issued_by: Optional[str] = None
    pts_issued_date: Optional[str] = None
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
        "client_birth_date",
        "client_birth_place",
        "client_passport",
        "client_passport_series",
        "client_passport_number",
        "client_passport_issued_by",
        "client_passport_issued_date",
        "client_passport_division_code",
        "client_address",
        "client_phone",
        "client_comment",
        "client_legal_name",
        "client_inn",
        "client_ogrn",
        "seller_fio",
        "seller_birth_date",
        "seller_passport",
        "seller_passport_series",
        "seller_passport_number",
        "seller_passport_issued_by",
        "seller_passport_issued_date",
        "seller_passport_division_code",
        "seller_address",
        "trustee_fio",
        "trustee_birth_date",
        "trustee_passport",
        "trustee_passport_series",
        "trustee_passport_number",
        "trustee_passport_issued_by",
        "trustee_passport_issued_date",
        "trustee_passport_division_code",
        "trustee_basis",
        "vin",
        "brand_model",
        "vehicle_type",
        "year",
        "engine",
        "chassis",
        "power",
        "mass",
        "body",
        "color",
        "srts",
        "srts_series",
        "srts_number",
        "srts_issued_by",
        "srts_issued_date",
        "plate_number",
        "pts",
        "pts_series",
        "pts_number",
        "pts_issued_by",
        "pts_issued_date",
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
        if len(digits) == 10:
            digits = "7" + digits
        elif len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) != 11 or not digits.startswith("7"):
            raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX")
        return "+" + digits

    @field_validator("vin")
    @classmethod
    def _validate_vin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return re.sub(r"\s+", "", value.upper())

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

    @field_validator("client_passport_series", "seller_passport_series", "trustee_passport_series")
    @classmethod
    def _validate_passport_series(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 4:
            raise ValueError("Серия паспорта должна содержать 4 цифры")
        return digits

    @field_validator("client_passport_number", "seller_passport_number", "trustee_passport_number")
    @classmethod
    def _validate_passport_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 6:
            raise ValueError("Номер паспорта должен содержать 6 цифр")
        return digits

    @field_validator("client_passport_division_code", "seller_passport_division_code", "trustee_passport_division_code")
    @classmethod
    def _validate_division_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) != 6:
            raise ValueError("Код подразделения должен содержать 6 цифр")
        return f"{digits[:3]}-{digits[3:]}"

    @field_validator("client_passport_issued_date", "seller_passport_issued_date", "trustee_passport_issued_date", "srts_issued_date", "pts_issued_date")
    @classmethod
    def _validate_document_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%d.%m.%Y")
        except ValueError as exc:
            raise ValueError("Дата выдачи должна быть в формате DD.MM.YYYY") from exc
        return value

    @field_validator("srts", "pts")
    @classmethod
    def _validate_vehicle_docs(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return re.sub(r"\s+", "", value.upper())

    @field_validator("srts_series", "pts_series")
    @classmethod
    def _validate_vehicle_doc_series(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", "", value.upper())
        if len(normalized) != 4:
            raise ValueError("Серия документа ТС должна содержать 4 символа")
        return normalized

    @field_validator("srts_number", "pts_number")
    @classmethod
    def _validate_vehicle_doc_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", "", value.upper())
        if len(normalized) != 6:
            raise ValueError("Номер документа ТС должен содержать 6 символов")
        return normalized

    @field_validator("dkp_date")
    @classmethod
    def _validate_dkp_date(cls, value: Optional[str]) -> Optional[str]:
        return validate_dkp_date(value)

    @field_validator("client_birth_date", "seller_birth_date", "trustee_birth_date")
    @classmethod
    def _validate_birth_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%d.%m.%Y")
        except ValueError as exc:
            raise ValueError("Дата рождения должна быть в формате DD.MM.YYYY") from exc
        return value

    @model_validator(mode="after")
    def _compose_split_documents(self):
        for prefix in ("client", "seller", "trustee"):
            series = getattr(self, f"{prefix}_passport_series")
            number = getattr(self, f"{prefix}_passport_number")
            combined_name = f"{prefix}_passport"
            if series and number:
                setattr(self, combined_name, f"{series} {number}")
            elif series or number:
                raise ValueError("Паспорт должен содержать серию 4 цифры и номер 6 цифр")

        for prefix in ("srts", "pts"):
            series = getattr(self, f"{prefix}_series")
            number = getattr(self, f"{prefix}_number")
            if series and number:
                setattr(self, prefix, f"{series} {number}")
            elif series or number:
                raise ValueError("Документ ТС должен содержать серию 4 символа и номер 6 символов")
        return self


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
    plate_document: str = "number.docx"
    created_at: str
