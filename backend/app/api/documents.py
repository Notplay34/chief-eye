from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireOrdersListAccess, UserInfo
from app.core.database import get_db
from app.models import Order
from app.services.docx_service import TEMPLATES_DIR, document_download_filename, render_docx
from app.services.errors import ServiceError
from app.services.order_access import ensure_can_print_template
from app.services.order_validation import validate_order_for_print
from app.services.template_registry import is_printable_template

router = APIRouter(prefix="/orders", tags=["documents"])

ALLOWED_TEMPLATES = [
    "akt_pp.docx",
    "DKP.docx",
    "dkp_dar.docx",
    "dkp_pieces.docx",
    "doverennost.docx",
    "mreo.docx",
    "number.docx",
    "prokuratura.docx",
    "zaiavlenie.docx",
    "zaiavlenie_na_nomera.docx",  # заявление на номера (для павильона 2)
]


def _template_allowed(name: str) -> bool:
    return name in ALLOWED_TEMPLATES and is_printable_template(name)


def _resolve_template(name: str) -> str:
    """Возвращает имя файла шаблона. Для заявления на номера — fallback на zaiavlenie.docx если отдельного файла нет."""
    if name == "zaiavlenie_na_nomera.docx" and not (TEMPLATES_DIR / name).is_file():
        if (TEMPLATES_DIR / "zaiavlenie.docx").is_file():
            return "zaiavlenie.docx"
    return name


@router.get("/{order_id}/documents/{template_name}", response_class=Response)
async def get_order_document(
    order_id: int,
    template_name: str,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireOrdersListAccess),
):
    resolved = _resolve_template(template_name)
    if not _template_allowed(resolved):
        raise HTTPException(status_code=404, detail="Шаблон не найден или недоступен")
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    try:
        ensure_can_print_template(_user, order, template_name)
        validate_order_for_print(order.form_data, template_name)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    try:
        data = render_docx(resolved, order.form_data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    filename = document_download_filename(template_name, order.form_data)
    encoded_filename = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
