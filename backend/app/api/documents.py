from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireFormAccess, RequireOrdersListAccess, UserInfo
from app.core.database import get_db
from app.models import Order
from app.services.docx_service import render_docx, TEMPLATES_DIR

router = APIRouter(prefix="/orders", tags=["documents"])

ALLOWED_TEMPLATES = [
    "akt_pp.docx",
    "DKP.docx",
    "dkp_dar.docx",
    "dkp_pieces.docx",
    "doverennost.docx",
    "mreo.docx",
    "number.docx",
    "obiasnenie.docx",
    "prokuratura.docx",
    "zaiavlenie.docx",
    "zaiavlenie_na_nomera.docx",  # заявление на номера (для павильона 2)
]


def _template_allowed(name: str) -> bool:
    return name in ALLOWED_TEMPLATES and (TEMPLATES_DIR / name).is_file()


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
        data = render_docx(resolved, order.form_data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{template_name}"'},
    )
