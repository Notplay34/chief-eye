from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireAnalyticsAccess, UserInfo
from app.core.database import get_db
from app.schemas.analytics import AnalyticsDashboard
from app.services.analytics_service import get_analytics_dashboard


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/today")
async def analytics_today(
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    dashboard = await get_analytics_dashboard(db, period="day", date_from=date_from, date_to=date_to, kind="all")
    return dashboard["overview"]


@router.get("/month")
async def analytics_month(
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    dashboard = await get_analytics_dashboard(db, period="month", date_from=date_from, date_to=date_to, kind="all")
    return dashboard["overview"]


@router.get("/employees")
async def analytics_employees(
    period: str = Query("month", description="day | week | month | quarter | year"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    kind: str = Query("all", description="all | docs | plates"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    dashboard = await get_analytics_dashboard(db, period=period, date_from=date_from, date_to=date_to, kind=kind)
    return {
        "period": dashboard["period"],
        "employees": dashboard["employee_stats"],
        "overview": dashboard["overview"],
    }


@router.get("/summary")
async def analytics_summary(
    period: str = Query("month", description="day | week | month | quarter | year"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    kind: str = Query("all", description="all | docs | plates"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    dashboard = await get_analytics_dashboard(db, period=period, date_from=date_from, date_to=date_to, kind=kind)
    return {
        "period": dashboard["period"],
        "current": dashboard["overview"],
        "previous": dashboard["previous_overview"],
        "status_breakdown": dashboard["status_breakdown"],
    }


@router.get("/dynamics")
async def analytics_dynamics(
    group_by: str = Query("month", description="month"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    kind: str = Query("all", description="all | docs | plates"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    dashboard = await get_analytics_dashboard(db, period="month", date_from=date_from, date_to=date_to, kind=kind)
    return {
        "group_by": group_by,
        "points": dashboard["monthly_trend"],
        "quarters": dashboard["quarter_summary"],
    }


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def analytics_dashboard(
    period: str = Query("month", description="day | week | month | quarter | year"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    kind: str = Query("all", description="all | docs | plates"),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    return await get_analytics_dashboard(db, period=period, date_from=date_from, date_to=date_to, kind=kind)


@router.get("/export")
async def analytics_export(
    format: str = Query("csv", description="csv"),
    period: str = Query("day", description="day | month | employees"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
):
    raise HTTPException(status_code=501, detail="Экспорт аналитики ещё не реализован")
