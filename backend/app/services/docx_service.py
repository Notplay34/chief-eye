"""
Генерация docx из шаблонов: подстановка плейсхолдеров {{...}} из данных заказа.
Шаблоны в папке templates/ в корне проекта (PROJECT_CONTEXT, раздел 13).
Используется простая замена строк (шаблоны с пробелами в плейсхолдерах, напр. «ФИО продавец»).
"""
from datetime import date
from pathlib import Path
from io import BytesIO
from typing import Dict, Optional

from docx import Document

# Папка шаблонов: корень проекта / templates
_BASE = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = _BASE / "templates"

# Маппинг: имя плейсхолдера в шаблоне (без {{ }}) → ключ в form_data
PLACEHOLDER_TO_FIELD = {
    "ФИО": "client_fio",
    "ФИО дов": "trustee_fio",
    "ФИО_подписант": "client_fio",
    "Паспорт": "client_passport",
    "Паспорт серия": "client_passport_series",
    "Паспорт номер": "client_passport_number",
    "Паспорт кем выдан": "client_passport_issued_by",
    "Паспорт когда выдан": "client_passport_issued_date",
    "Код подразделения": "client_passport_division_code",
    "Паспорт дов": "trustee_passport",
    "Паспорт дов серия": "trustee_passport_series",
    "Паспорт дов номер": "trustee_passport_number",
    "Паспорт дов кем выдан": "trustee_passport_issued_by",
    "Паспорт дов когда выдан": "trustee_passport_issued_date",
    "Код подразделения дов": "trustee_passport_division_code",
    "Адрес": "client_address",
    "Адрес дов": "client_address",
    "Телефон": "client_phone",
    "Номер телефона": "client_phone",
    "Номер телефона дов": "client_phone",
    "ФИО продавец": "seller_fio",
    "Паспорт продавец": "seller_passport",
    "Паспорт продавец серия": "seller_passport_series",
    "Паспорт продавец номер": "seller_passport_number",
    "Паспорт продавец кем выдан": "seller_passport_issued_by",
    "Паспорт продавец когда выдан": "seller_passport_issued_date",
    "Код подразделения продавец": "seller_passport_division_code",
    "Адрес продавец": "seller_address",
    "VIN": "vin",
    "Марка, модель": "brand_model",
    "Тип ТС": "vehicle_type",
    "Год выпуска": "year",
    "Двигатель": "engine",
    "№ шасси (рамы)": "chassis",
    "№ кузова": "body",
    "Цвет": "color",
    "СРТС": "srts",
    "СРТС серия": "srts_series",
    "СРТС номер": "srts_number",
    "СРТС кем выдан": "srts_issued_by",
    "СРТС когда выдан": "srts_issued_date",
    "Гос. Номер": "plate_number",
    "ПТС": "pts",
    "ПТС серия": "pts_series",
    "ПТС номер": "pts_number",
    "ПТС кем выдан": "pts_issued_by",
    "ПТС когда выдан": "pts_issued_date",
    "Сумма ДКП": "summa_dkp",
    "Дата ДКП": "dkp_date",
    "Номер договора": "dkp_number",
    "ДКП": "dkp_summary",
    "Название": "client_legal_name",
    "ИНН": "client_inn",
    "ОГРН": "client_ogrn",
    "Сумма госпошлины": "state_duty",
    "Подпись": "client_fio",
    "Дата рождения": None,
    "Место рождения": None,
    "Масса": None,
    "Мощность": None,
    "ОСАГО": None,
    "Текущая_дата": None,
}

_PASSPORT_PLACEHOLDER_PREFIXES = {
    "Паспорт": "client",
    "Паспорт продавец": "seller",
    "Паспорт дов": "trustee",
}

_REPRESENTATIVE_TEMPLATES = frozenset({"zaiavlenie.docx"})


def _fio_initials(value: Optional[str]) -> str:
    """Возвращает расшифровку подписи в формате Фамилия И.О."""
    if not value:
        return ""
    parts = [part for part in str(value).split() if part]
    if len(parts) < 2:
        return str(value).strip()
    initials = "".join(f"{part[0]}." for part in parts[1:] if part)
    return f"{parts[0]} {initials}".strip()


def _full_passport(form_data: dict, prefix: str) -> str:
    passport = form_data.get(f"{prefix}_passport")
    series = form_data.get(f"{prefix}_passport_series")
    number = form_data.get(f"{prefix}_passport_number")
    if not passport and series and number:
        passport = f"{series} {number}"

    parts = [str(passport).strip()] if passport else []
    issued_by = form_data.get(f"{prefix}_passport_issued_by")
    issued_date = form_data.get(f"{prefix}_passport_issued_date")
    division_code = form_data.get(f"{prefix}_passport_division_code")
    if issued_by:
        parts.append(f"выдан {str(issued_by).strip()}")
    if issued_date:
        parts.append(str(issued_date).strip())
    if division_code:
        parts.append(f"код подразделения {str(division_code).strip()}")
    return ", ".join(part for part in parts if part)


def _signature_fio(form_data: dict, template_name: Optional[str]) -> str:
    if template_name in _REPRESENTATIVE_TEMPLATES and form_data.get("trustee_fio"):
        return _fio_initials(form_data.get("trustee_fio"))
    return _fio_initials(form_data.get("client_fio"))


def _form_data_to_replace_map(
    form_data: Optional[dict],
    doc_date: Optional[date] = None,
    template_name: Optional[str] = None,
) -> Dict[str, str]:
    """Словарь подстановки: «{{ ключ }}» → значение."""
    if not form_data:
        form_data = {}
    doc_date = doc_date or date.today()
    result = {}
    for placeholder, field_key in PLACEHOLDER_TO_FIELD.items():
        value = form_data.get(field_key) if field_key else None
        if placeholder in _PASSPORT_PLACEHOLDER_PREFIXES:
            value = _full_passport(form_data, _PASSPORT_PLACEHOLDER_PREFIXES[placeholder])
        if placeholder in {"Подпись", "ФИО_подписант"}:
            value = _signature_fio(form_data, template_name)
        if value is None and placeholder == "Текущая_дата":
            value = doc_date.strftime("%d.%m.%Y")
        if value is None and placeholder == "Дата ДКП":
            value = doc_date.strftime("%d.%m.%Y")
        if value is None and placeholder == "ДКП":
            parts = []
            if form_data.get("dkp_date"):
                parts.append(str(form_data["dkp_date"]))
            if form_data.get("summa_dkp"):
                parts.append(str(form_data["summa_dkp"]))
            if form_data.get("dkp_number"):
                parts.append("№ " + str(form_data["dkp_number"]))
            value = ", ".join(parts) if parts else ""
        if value is None:
            value = ""
        result[placeholder] = str(value)
    return result


def _replace_in_paragraph(paragraph, replace_map: dict[str, str]) -> None:
    text = paragraph.text
    for key, value in replace_map.items():
        text = text.replace("{{" + key + "}}", value)
        text = text.replace("{{ " + key + " }}", value)
    if text != paragraph.text:
        paragraph.clear()
        paragraph.add_run(text)


def render_docx(template_name: str, form_data: Optional[dict], doc_date: Optional[date] = None) -> bytes:
    """
    Генерирует docx из шаблона (например DKP.docx), подставляя {{ плейсхолдер }} из form_data.
    Возвращает файл как bytes.
    """
    path = TEMPLATES_DIR / template_name
    if not path.is_file():
        raise FileNotFoundError(f"Шаблон не найден: {template_name}")
    doc = Document(str(path))
    replace_map = _form_data_to_replace_map(form_data, doc_date, template_name)
    for p in doc.paragraphs:
        _replace_in_paragraph(p, replace_map)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_in_paragraph(p, replace_map)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
