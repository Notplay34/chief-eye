"""Scenario-based order and print validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.services.errors import ServiceError

FIELD_LABELS = {
    "client_fio": "ФИО клиента",
    "client_passport": "Паспорт клиента",
    "client_address": "Адрес клиента",
    "client_phone": "Телефон клиента",
    "client_legal_name": "Название юрлица",
    "client_inn": "ИНН",
    "client_ogrn": "ОГРН",
    "seller_fio": "ФИО продавца",
    "seller_passport": "Паспорт продавца",
    "seller_address": "Адрес продавца",
    "trustee_fio": "ФИО доверенного лица",
    "trustee_passport": "Паспорт доверенного лица",
    "vin": "VIN",
    "brand_model": "Марка/модель",
    "vehicle_type": "Тип ТС",
    "year": "Год выпуска",
    "engine": "Двигатель",
    "chassis": "№ шасси (рамы)",
    "body": "№ кузова",
    "color": "Цвет",
    "srts": "СРТС",
    "plate_number": "Госномер",
    "pts": "ПТС",
    "dkp_date": "Дата ДКП",
    "summa_dkp": "Сумма ДКП",
    "state_duty": "Госпошлина",
}

TEMPLATE_REQUIRED_FIELDS = {
    "zaiavlenie.docx": {
        "client_fio", "client_passport", "client_address", "client_phone", "vin",
        "brand_model", "year", "vehicle_type", "state_duty",
    },
    "DKP.docx": {
        "client_fio", "client_passport", "client_address",
        "seller_fio", "seller_passport", "seller_address",
        "vin", "brand_model", "year",
        "summa_dkp", "dkp_date",
    },
    "akt_pp.docx": {
        "client_fio", "client_passport", "client_address",
        "seller_fio", "seller_passport", "seller_address",
        "vin", "brand_model", "year",
        "dkp_date",
    },
    "dkp_dar.docx": {
        "client_fio", "client_passport", "client_address",
        "seller_fio", "seller_passport", "seller_address",
        "vin", "brand_model", "year", "dkp_date",
    },
    "dkp_pieces.docx": {
        "client_fio", "client_passport", "client_address",
        "seller_fio", "seller_passport", "seller_address",
        "vin", "brand_model", "year", "dkp_date", "vehicle_type",
    },
    "doverennost.docx": {
        "client_fio", "client_passport", "client_address",
        "trustee_fio", "trustee_passport",
        "vin", "brand_model", "year",
    },
    "mreo.docx": {"client_fio", "client_passport", "client_address", "client_phone", "brand_model", "year"},
    "number.docx": {"client_fio", "client_passport", "client_address", "client_phone", "vin", "brand_model", "year"},
    "prokuratura.docx": {"client_fio", "client_passport", "client_address", "client_phone"},
    "zaiavlenie_na_nomera.docx": {
        "client_fio", "client_passport", "client_address", "client_phone", "vin",
        "brand_model", "year",
    },
}

TEMPLATE_CREATE_REQUIRED_FIELDS = {
    "zaiavlenie.docx": {"client_fio", "brand_model"},
    "DKP.docx": {"client_fio", "seller_fio", "seller_passport", "brand_model", "summa_dkp"},
    "akt_pp.docx": {"client_fio", "seller_fio", "seller_passport", "brand_model"},
    "dkp_dar.docx": {"client_fio", "seller_fio", "seller_passport", "brand_model"},
    "dkp_pieces.docx": {"client_fio", "seller_fio", "seller_passport", "brand_model"},
    "doverennost.docx": {"client_fio", "trustee_fio", "trustee_passport", "brand_model"},
    "mreo.docx": {"client_fio", "brand_model"},
    "number.docx": {"client_fio", "brand_model"},
    "prokuratura.docx": {"client_fio"},
    "zaiavlenie_na_nomera.docx": {"client_fio", "brand_model"},
}


def _as_dict(data: Any) -> dict:
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    raise TypeError("Order validation expects a dict-like object or Pydantic model")


def _field_has_value(data: dict, field: str) -> bool:
    value = data.get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _required_fields_for_payload(data: dict, template_name: str, required_map: dict[str, set[str]]) -> set[str]:
    required = set(required_map.get(template_name, set()))
    if data.get("client_is_legal"):
        if "client_fio" in required:
            required.remove("client_fio")
            required.add("client_legal_name")
        if "client_passport" in required:
            required.remove("client_passport")
            required.add("trustee_passport")
        required.add("trustee_fio")
    return required


def _missing_fields(data: dict, template_name: str, required_map: dict[str, set[str]]) -> list[str]:
    required = _required_fields_for_payload(data, template_name, required_map)
    missing = [FIELD_LABELS.get(field, field) for field in required if not _field_has_value(data, field)]
    return sorted(missing)


def validate_create_order_data(data: Any, templates: list[str]) -> None:
    payload = _as_dict(data)
    missing: dict[str, list[str]] = {}
    for template_name in templates:
        template_missing = _missing_fields(payload, template_name, TEMPLATE_CREATE_REQUIRED_FIELDS)
        if template_missing:
            missing[template_name] = template_missing
    if missing:
        messages = [f"{template}: {', '.join(fields)}" for template, fields in missing.items()]
        raise ServiceError("Недостаточно данных для заказа: " + "; ".join(messages), status_code=400)


def validate_order_for_print(order_data: Optional[dict], template_name: str) -> None:
    payload = _as_dict(order_data)
    missing = _missing_fields(payload, template_name, TEMPLATE_REQUIRED_FIELDS)
    if missing:
        raise ServiceError(
            f"Для печати {template_name} не хватает данных: {', '.join(missing)}",
            status_code=400,
        )


def validate_dkp_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        datetime.strptime(value, "%d.%m.%Y")
    except ValueError as exc:
        raise ValueError("Дата ДКП должна быть в формате DD.MM.YYYY") from exc
    return value
