from typing import Optional
import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
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
    kind: str = Query("all", description="all | docs | plates"),
    _user: UserInfo = Depends(RequireAnalyticsAccess),
    db: AsyncSession = Depends(get_db),
):
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Поддерживается только csv")

    dashboard = await get_analytics_dashboard(db, period=period, date_from=date_from, date_to=date_to, kind=kind)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Раздел", "Показатель", "Значение", "Дополнительно 1", "Дополнительно 2"])

    overview = dashboard["overview"]
    for key, value in overview.items():
        writer.writerow(["Сводка", key, value, "", ""])

    for row in dashboard["employee_stats"]:
        writer.writerow([
            "Сотрудники",
            row.get("employee_name", ""),
            f"Заказов: {row.get('orders_count', 0)}",
            f"Доход: {row.get('income_total', 0)}",
            f"Средний чек: {row.get('average_check', 0)}",
        ])

    for row in dashboard["status_breakdown"]:
        writer.writerow([
            "Статусы",
            row.get("status", ""),
            row.get("count", 0),
            "",
            "",
        ])

    for row in dashboard["monthly_trend"]:
        writer.writerow([
            "Динамика по месяцам",
            row.get("period_key", ""),
            row.get("orders_count", 0),
            row.get("income_total", 0),
            row.get("turnover_total", 0),
        ])

    filename = f"analytics_{kind}_{period}.csv"
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
