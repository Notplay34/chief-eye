"""История заполнения формы: список записей для подстановки в форму."""
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireFormAccess, UserInfo
from app.core.database import get_db
from app.models import FormHistory

router = APIRouter(prefix="/form-history", tags=["form-history"])


@router.get("")
async def list_form_history(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0, le=100000),
    business_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireFormAccess),
):
    """Список записей истории (последние сверху). Для подстановки в форму по клику."""
    q = select(FormHistory).order_by(FormHistory.id.desc()).offset(offset).limit(limit)
    if business_date is not None:
        start = datetime.combine(business_date, time.min)
        end = datetime.combine(business_date, time.max)
        q = q.where(FormHistory.created_at >= start, FormHistory.created_at <= end)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "order_id": r.order_id,
            "form_data": r.form_data,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
