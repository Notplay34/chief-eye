from decimal import Decimal
from pydantic import BaseModel
from typing import List


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
