from decimal import Decimal
from typing import List

from pydantic import BaseModel


class BaseAnalyticsBlock(BaseModel):
    """Базовый набор финансовых показателей за период."""

    total_revenue: Decimal
    state_duty_total: Decimal
    net_income: Decimal
    income_pavilion1: Decimal
    income_pavilion2: Decimal
    orders_count: int
    average_check: Decimal


class TodayAnalytics(BaseAnalyticsBlock):
    """Сводка за день (устаревший эндпоинт, обёртка над summary)."""
    pass


class MonthAnalytics(BaseAnalyticsBlock):
    """Сводка за месяц (устаревший эндпоинт, обёртка над summary)."""
    pass


class SummaryAnalytics(BaseModel):
    """Текущий и предыдущий период для управленческой аналитики."""

    period: str  # day | week | month
    current: BaseAnalyticsBlock
    previous: BaseAnalyticsBlock


class DynamicsPoint(BaseModel):
    """Точка динамики по периоду (день/неделя/месяц)."""

    period_start: str  # ISO date string
    total_revenue: Decimal
    net_income: Decimal
    income_pavilion1: Decimal
    income_pavilion2: Decimal
    orders_count: int


class DynamicsAnalytics(BaseModel):
    group_by: str  # day | week | month
    points: List[DynamicsPoint]


class EmployeeStat(BaseModel):
    employee_id: int
    employee_name: str
    orders_count: int
    total_amount: Decimal
    average_check: Decimal
    share_percent: Decimal


class EmployeesAnalytics(BaseModel):
    period: str  # "day" | "week" | "month"
    total_revenue: Decimal
    employees: List[EmployeeStat]


class AnalyticsPeriod(BaseModel):
    kind: str
    period: str
    date_from: str
    date_to: str
    days: int
    previous_date_from: str
    previous_date_to: str


class AnalyticsOverview(BaseModel):
    orders_count: int
    turnover_total: Decimal
    income_total: Decimal
    state_duty_total: Decimal
    state_duty_cash_total: Decimal
    state_duty_commission_income: Decimal
    insurance_commission_income: Decimal
    docs_income: Decimal
    plates_income: Decimal
    plate_extra_income: Decimal
    average_check: Decimal
    numbers_orders_count: int
    numbers_units: int


class AnalyticsStatusItem(BaseModel):
    status: str
    count: int


class AnalyticsTrendItem(BaseModel):
    period_key: str
    label: str
    orders_count: int
    turnover_total: Decimal
    income_total: Decimal
    docs_income: Decimal | None = None
    state_duty_commission_income: Decimal | None = None
    insurance_commission_income: Decimal | None = None


class AnalyticsEmployeeItem(BaseModel):
    employee_id: int
    employee_name: str
    orders_count: int
    income_total: Decimal
    average_check: Decimal
    share_percent: Decimal


class AnalyticsServiceItem(BaseModel):
    label: str
    count: int
    revenue: Decimal


class AnalyticsDashboard(BaseModel):
    period: AnalyticsPeriod
    overview: AnalyticsOverview
    previous_overview: AnalyticsOverview
    status_breakdown: List[AnalyticsStatusItem]
    monthly_trend: List[AnalyticsTrendItem]
    quarter_summary: List[AnalyticsTrendItem]
    employee_stats: List[AnalyticsEmployeeItem]
    top_services: List[AnalyticsServiceItem]
