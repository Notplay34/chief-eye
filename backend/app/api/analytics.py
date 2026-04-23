from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import RequireAnalyticsAccess, UserInfo


router = APIRouter(prefix="/analytics", tags=["analytics"])


def _analytics_disabled() -> None:
    """
    Общий helper для всех эндпоинтов аналитики.

    Временно отключает функциональность и сообщает,
    что раздел находится в разработке.
    """

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Аналитика временно отключена (функция в разработке).",
    )


@router.get("/today")
async def analytics_today(
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()


@router.get("/month")
async def analytics_month(
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()


@router.get("/employees")
async def analytics_employees(
    period: str = Query("day", description="day | week | month"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    kind: str = Query("all", description="all | docs | plates"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()


@router.get("/summary")
async def analytics_summary(
    period: str = Query("day", description="day | week | month"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()


@router.get("/dynamics")
async def analytics_dynamics(
    group_by: str = Query("day", description="day | week | month"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()


@router.get("/export")
async def analytics_export(
    format: str = Query("csv", description="csv"),
    period: str = Query("day", description="day | month | employees"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    _analytics_disabled()

