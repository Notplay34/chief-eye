from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireAdmin, RequireFormAccess, UserInfo
from app.core.database import get_db
from app.models import DocumentPrice

router = APIRouter(prefix="/price-list", tags=["price-list"])


def _row_to_dict(row: DocumentPrice) -> dict:
    return {
        "id": row.id,
        "template": row.template,
        "label": row.label,
        "price": float(row.price) if row.price is not None else 0,
        "sort_order": row.sort_order,
    }


@router.get("")
async def get_price_list(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireFormAccess),
):
    """Прейскурант: список документов с ценами (для формы и админки)."""
    r = await db.execute(
        select(DocumentPrice).order_by(DocumentPrice.sort_order, DocumentPrice.id)
    )
    rows = r.scalars().all()
    return [_row_to_dict(row) for row in rows]


class PriceListItemUpdate(BaseModel):
    template: str
    label: str
    price: Decimal = Field(..., ge=0)
    sort_order: int = 0


@router.put("")
async def update_price_list(
    items: List[PriceListItemUpdate],
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAdmin),
):
    """Обновить прейскурант (только админ). Передаётся полный список позиций."""
    sent_templates = {item.template for item in items}
    r = await db.execute(select(DocumentPrice))
    existing = {row.template: row for row in r.scalars().all()}
    for i, item in enumerate(items):
        row = existing.get(item.template)
        sort = item.sort_order if item.sort_order else i
        if row:
            row.label = item.label
            row.price = item.price
            row.sort_order = sort
        else:
            db.add(
                DocumentPrice(
                    template=item.template,
                    label=item.label,
                    price=item.price,
                    sort_order=sort,
                )
            )
    if sent_templates:
        await db.execute(delete(DocumentPrice).where(DocumentPrice.template.notin_(sent_templates)))
    await db.commit()
    r = await db.execute(
        select(DocumentPrice).order_by(DocumentPrice.sort_order, DocumentPrice.id)
    )
    rows = r.scalars().all()
    return [_row_to_dict(row) for row in rows]
