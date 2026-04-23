"""Склад заготовок номеров: остатки, пополнение, резерв, списание."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequirePlateAccess, UserInfo
from app.core.database import get_db
from app.services.errors import ServiceError
from app.services.warehouse_service import (
    add_plate_stock as add_plate_stock_service,
    build_plate_stock_summary,
    register_plate_defect,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("")
async def warehouse_root():
    """Проверка, что модуль склада подключён."""
    return {"status": "ok", "module": "warehouse"}


@router.get("/plate-stock")
async def get_plate_stock(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Текущий остаток, зарезервировано по невыданным заказам (PAID, PLATE_IN_PROGRESS, PLATE_READY)."""
    try:
        return await build_plate_stock_summary(db)
    except ServiceError as exc:
        _raise_service_error(exc)


class AddStockBody(BaseModel):
    amount: int


@router.post("/plate-stock/add")
async def add_plate_stock(
    body: AddStockBody,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Пополнить склад заготовок."""
    try:
        return await add_plate_stock_service(db, body.amount)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.post("/plate-stock/defect")
async def add_plate_defect(
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequirePlateAccess),
):
    """Списать 1 шт как брак (вычитается из остатка, учитывается в счётчике за месяц)."""
    try:
        return await register_plate_defect(db)
    except ServiceError as exc:
        _raise_service_error(exc)
