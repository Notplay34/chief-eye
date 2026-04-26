from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Order, OrderStatus, Payment, PaymentType
from app.services.errors import ServiceError

PLATE_TEMPLATE = "number.docx"
ZERO = Decimal("0")
REVENUE_ORDER_STATUSES = {
    OrderStatus.PAID,
    OrderStatus.PLATE_IN_PROGRESS,
    OrderStatus.PLATE_READY,
    OrderStatus.COMPLETED,
}


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ServiceError("Дата должна быть в формате YYYY-MM-DD", status_code=400) from exc


def resolve_period(
    period: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> tuple[date, date]:
    start = _parse_date(date_from)
    end = _parse_date(date_to)
    today = datetime.utcnow().date()

    if start and end:
        if start > end:
            raise ServiceError("Начало периода не может быть позже конца", status_code=400)
        return start, end

    if start and not end:
        return start, today
    if end and not start:
        raise ServiceError("Если указан date_to, нужно указать и date_from", status_code=400)

    period_key = (period or "month").lower()
    if period_key == "day":
        return today, today
    if period_key == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period_key == "month":
        return date(today.year, today.month, 1), today
    if period_key == "quarter":
        start_month = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, start_month, 1), today
    if period_key == "year":
        return date(today.year, 1, 1), today

    raise ServiceError("period должен быть one of: day, week, month, quarter, year", status_code=400)


def _period_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)


def _docs_for_order(order: Order) -> list[dict]:
    form_data = order.form_data or {}
    docs = form_data.get("documents") or []
    return docs if isinstance(docs, list) else []


def _split_order_revenue(order: Order) -> tuple[Decimal, Decimal]:
    docs_income = ZERO
    plates_income = ZERO
    for item in _docs_for_order(order):
        template = (item.get("template") or "").strip().lower()
        price = _to_decimal(item.get("price"))
        if template == PLATE_TEMPLATE:
            plates_income += price
        else:
            docs_income += price
    if order.need_plate:
        plates_income += _to_decimal(order.income_pavilion2)
    return docs_income, plates_income


def _state_duty_parts(order: Order) -> tuple[Decimal, Decimal, Decimal]:
    form_data = order.form_data or {}
    base = _to_decimal(form_data.get("state_duty_base_amount") or order.state_duty_amount)
    commission = _to_decimal(form_data.get("state_duty_commission"))
    cash_amount = _to_decimal(form_data.get("state_duty_cash_amount"))
    if cash_amount <= 0 and base > 0:
        cash_amount = base + commission
    if commission <= 0 and cash_amount > base:
        commission = cash_amount - base
    return base, commission, cash_amount


def _scope_match(order: Order, kind: str) -> bool:
    kind_key = (kind or "all").lower()
    if kind_key == "all":
        return True
    if kind_key == "plates":
        return bool(order.need_plate)
    if kind_key == "docs":
        return True
    raise ServiceError("kind должен быть one of: all, docs, plates", status_code=400)


def _order_income_for_kind(order: Order, kind: str) -> Decimal:
    docs_income, plates_income = _split_order_revenue(order)
    _base, state_duty_commission, _cash_amount = _state_duty_parts(order)
    if kind == "docs":
        return docs_income + state_duty_commission
    if kind == "plates":
        return plates_income
    return docs_income + plates_income + state_duty_commission


def _build_overview(
    orders: Iterable[Order],
    extra_payments: Iterable[Payment],
    kind: str,
) -> dict:
    scope_orders = [order for order in orders if _scope_match(order, kind)]

    docs_income = ZERO
    plates_income = ZERO
    state_duty_total = ZERO
    state_duty_cash_total = ZERO
    state_duty_commission_income = ZERO
    numbers_orders_count = 0
    numbers_units = 0
    status_breakdown: dict[str, int] = defaultdict(int)

    for order in scope_orders:
        order_docs_income, order_plates_income = _split_order_revenue(order)
        state_duty_base, state_duty_commission, state_duty_cash = _state_duty_parts(order)
        docs_income += order_docs_income
        plates_income += order_plates_income
        state_duty_total += state_duty_base
        state_duty_cash_total += state_duty_cash
        state_duty_commission_income += state_duty_commission
        status_breakdown[order.status.value] += 1
        if order.need_plate:
            numbers_orders_count += 1
            form_data = order.form_data or {}
            numbers_units += max(1, int(form_data.get("plate_quantity") or 1))

    plate_extra_income = sum((_to_decimal(payment.amount) for payment in extra_payments), ZERO)

    docs_income_output = docs_income if kind in ("all", "docs") else ZERO
    plates_income_output = plates_income if kind in ("all", "plates") else ZERO
    plate_extra_output = plate_extra_income if kind in ("all", "plates") else ZERO
    state_duty_output = state_duty_total if kind in ("all", "docs") else ZERO
    state_duty_cash_output = state_duty_cash_total if kind in ("all", "docs") else ZERO
    state_duty_commission_output = state_duty_commission_income if kind in ("all", "docs") else ZERO

    income_total = docs_income_output + plates_income_output + plate_extra_output + state_duty_commission_output
    turnover_total = income_total + state_duty_output
    orders_count = len(scope_orders)
    average_check = (turnover_total / orders_count) if orders_count else ZERO

    return {
        "orders_count": orders_count,
        "turnover_total": turnover_total,
        "income_total": income_total,
        "state_duty_total": state_duty_output,
        "state_duty_cash_total": state_duty_cash_output,
        "state_duty_commission_income": state_duty_commission_output,
        "docs_income": docs_income_output,
        "plates_income": plates_income_output,
        "plate_extra_income": plate_extra_output,
        "average_check": average_check,
        "numbers_orders_count": numbers_orders_count if kind in ("all", "plates") else 0,
        "numbers_units": numbers_units if kind in ("all", "plates") else 0,
        "status_breakdown": [
            {"status": status, "count": count}
            for status, count in sorted(status_breakdown.items(), key=lambda item: item[1], reverse=True)
        ],
    }


def _month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _quarter_label(day: date) -> str:
    quarter = ((day.month - 1) // 3) + 1
    return f"Q{quarter} {day.year}"


async def _fetch_orders(db: AsyncSession, start: date, end: date) -> list[Order]:
    start_dt, end_dt = _period_bounds(start, end)
    result = await db.execute(
        select(Order)
        .where(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status.in_(REVENUE_ORDER_STATUSES),
        )
        .order_by(Order.created_at)
    )
    return result.scalars().all()


async def _fetch_extra_payments(db: AsyncSession, start: date, end: date) -> list[Payment]:
    start_dt, end_dt = _period_bounds(start, end)
    result = await db.execute(
        select(Payment)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Payment.created_at >= start_dt,
            Payment.created_at < end_dt,
            Payment.type == PaymentType.INCOME_PAVILION2,
            Order.status.in_(REVENUE_ORDER_STATUSES),
        )
    )
    return result.scalars().all()


async def _employee_names(db: AsyncSession) -> dict[int, str]:
    result = await db.execute(select(Employee.id, Employee.name))
    return {employee_id: name for employee_id, name in result.all()}


def _build_monthly_trend(
    orders: list[Order],
    extra_payments: list[Payment],
    kind: str,
    end: date,
) -> list[dict]:
    month_starts = []
    current = date(end.year, end.month, 1)
    for _ in range(12):
        month_starts.append(current)
        if current.month == 1:
            current = date(current.year - 1, 12, 1)
        else:
            current = date(current.year, current.month - 1, 1)
    month_starts.reverse()

    orders_by_month: dict[str, list[Order]] = defaultdict(list)
    for order in orders:
        orders_by_month[_month_key(order.created_at.date())].append(order)

    extras_by_month: dict[str, list[Payment]] = defaultdict(list)
    for payment in extra_payments:
        extras_by_month[_month_key(payment.created_at.date())].append(payment)

    points = []
    for month_start in month_starts:
        key = _month_key(month_start)
        overview = _build_overview(orders_by_month.get(key, []), extras_by_month.get(key, []), kind)
        points.append({
            "period_key": key,
            "label": month_start.strftime("%m.%Y"),
            "orders_count": overview["orders_count"],
            "turnover_total": overview["turnover_total"],
            "income_total": overview["income_total"],
        })
    return points


def _build_quarter_summary(
    orders: list[Order],
    extra_payments: list[Payment],
    kind: str,
    end: date,
) -> list[dict]:
    year = end.year
    orders_by_quarter: dict[str, list[Order]] = defaultdict(list)
    for order in orders:
        created = order.created_at.date()
        if created.year != year:
            continue
        orders_by_quarter[_quarter_label(created)].append(order)

    extras_by_quarter: dict[str, list[Payment]] = defaultdict(list)
    for payment in extra_payments:
        created = payment.created_at.date()
        if created.year != year:
            continue
        extras_by_quarter[_quarter_label(created)].append(payment)

    rows = []
    for quarter in range(1, 5):
        label = f"Q{quarter} {year}"
        overview = _build_overview(orders_by_quarter.get(label, []), extras_by_quarter.get(label, []), kind)
        rows.append({
            "period_key": f"{year}-Q{quarter}",
            "label": label,
            "orders_count": overview["orders_count"],
            "turnover_total": overview["turnover_total"],
            "income_total": overview["income_total"],
        })
    return rows


def _build_employee_stats(
    orders: list[Order],
    extra_payments: list[Payment],
    employee_names: dict[int, str],
    kind: str,
    total_income: Decimal,
) -> list[dict]:
    stats: dict[int, dict] = {}
    for order in orders:
        if not _scope_match(order, kind):
            continue
        employee_id = order.employee_id
        if not employee_id:
            continue
        stats.setdefault(employee_id, {"orders_count": 0, "income_total": ZERO})
        stats[employee_id]["orders_count"] += 1
        stats[employee_id]["income_total"] += _order_income_for_kind(order, kind)

    if kind in ("all", "plates"):
        for payment in extra_payments:
            if not payment.employee_id:
                continue
            stats.setdefault(payment.employee_id, {"orders_count": 0, "income_total": ZERO})
            stats[payment.employee_id]["income_total"] += _to_decimal(payment.amount)

    rows = []
    for employee_id, values in stats.items():
        income_total = values["income_total"]
        orders_count = values["orders_count"]
        rows.append({
            "employee_id": employee_id,
            "employee_name": employee_names.get(employee_id, f"Сотрудник #{employee_id}"),
            "orders_count": orders_count,
            "income_total": income_total,
            "average_check": (income_total / orders_count) if orders_count else ZERO,
            "share_percent": ((income_total / total_income) * Decimal("100")) if total_income else ZERO,
        })
    rows.sort(key=lambda item: (item["income_total"], item["orders_count"]), reverse=True)
    return rows


def _build_top_services(orders: list[Order], extra_payments: list[Payment], kind: str) -> list[dict]:
    stats: dict[str, dict] = {}
    for order in orders:
        if not _scope_match(order, kind):
            continue
        _state_duty_base, state_duty_commission, _state_duty_cash = _state_duty_parts(order)
        for item in _docs_for_order(order):
            template = (item.get("template") or "").strip().lower()
            is_plate = template == PLATE_TEMPLATE
            if kind == "docs" and is_plate:
                continue
            if kind == "plates" and not is_plate:
                continue
            label = (item.get("label") or item.get("template") or "Без названия").strip()
            price = _to_decimal(item.get("price"))
            stats.setdefault(label, {"label": label, "count": 0, "revenue": ZERO})
            stats[label]["count"] += 1
            stats[label]["revenue"] += price
        if order.need_plate and kind in ("all", "plates"):
            label = "Изготовление номера"
            stats.setdefault(label, {"label": label, "count": 0, "revenue": ZERO})
            stats[label]["count"] += 1
            stats[label]["revenue"] += _to_decimal(order.income_pavilion2)
        if state_duty_commission > 0 and kind in ("all", "docs"):
            label = "Комиссия госпошлины"
            stats.setdefault(label, {"label": label, "count": 0, "revenue": ZERO})
            stats[label]["count"] += 1
            stats[label]["revenue"] += state_duty_commission

    if kind in ("all", "plates") and extra_payments:
        stats.setdefault("Доплата за номера", {"label": "Доплата за номера", "count": 0, "revenue": ZERO})
        for payment in extra_payments:
            stats["Доплата за номера"]["count"] += 1
            stats["Доплата за номера"]["revenue"] += _to_decimal(payment.amount)

    rows = list(stats.values())
    rows.sort(key=lambda item: (item["revenue"], item["count"]), reverse=True)
    return rows[:8]


async def get_analytics_dashboard(
    db: AsyncSession,
    period: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    kind: str = "all",
) -> dict:
    kind_key = (kind or "all").lower()
    start, end = resolve_period(period=period, date_from=date_from, date_to=date_to)
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)

    current_orders = await _fetch_orders(db, start, end)
    current_extra_payments = await _fetch_extra_payments(db, start, end)
    previous_orders = await _fetch_orders(db, previous_start, previous_end)
    previous_extra_payments = await _fetch_extra_payments(db, previous_start, previous_end)

    trend_start = date(end.year, end.month, 1)
    for _ in range(11):
        if trend_start.month == 1:
            trend_start = date(trend_start.year - 1, 12, 1)
        else:
            trend_start = date(trend_start.year, trend_start.month - 1, 1)
    trend_orders = await _fetch_orders(db, trend_start, end)
    trend_extras = await _fetch_extra_payments(db, trend_start, end)

    year_start = date(end.year, 1, 1)
    year_end = date(end.year, 12, 31)
    year_orders = await _fetch_orders(db, year_start, year_end)
    year_extras = await _fetch_extra_payments(db, year_start, year_end)

    employee_names = await _employee_names(db)
    overview = _build_overview(current_orders, current_extra_payments, kind_key)
    previous_overview = _build_overview(previous_orders, previous_extra_payments, kind_key)

    return {
        "period": {
            "kind": kind_key,
            "period": period,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "days": days,
            "previous_date_from": previous_start.isoformat(),
            "previous_date_to": previous_end.isoformat(),
        },
        "overview": {key: value for key, value in overview.items() if key != "status_breakdown"},
        "previous_overview": {key: value for key, value in previous_overview.items() if key != "status_breakdown"},
        "status_breakdown": overview["status_breakdown"],
        "monthly_trend": _build_monthly_trend(trend_orders, trend_extras, kind_key, end),
        "quarter_summary": _build_quarter_summary(year_orders, year_extras, kind_key, end),
        "employee_stats": _build_employee_stats(
            current_orders,
            current_extra_payments,
            employee_names,
            kind_key,
            overview["income_total"],
        ),
        "top_services": _build_top_services(current_orders, current_extra_payments, kind_key),
    }
