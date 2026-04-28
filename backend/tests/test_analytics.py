"""Базовые сценарии аналитики."""

from decimal import Decimal
from datetime import date, timedelta

from fastapi.testclient import TestClient


def as_float(value) -> float:
    return float(Decimal(str(value)))


def make_order_payload(*, need_plate: bool = False, plate_quantity: int = 1) -> dict:
    documents = [
        {"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"},
    ]
    return {
        "client_fio": "Иван Иванов",
        "brand_model": "Lada Vesta",
        "state_duty": "500",
        "need_plate": need_plate,
        "plate_quantity": plate_quantity,
        "documents": documents,
        "extra_amount": "0",
        "plate_amount": str(1500 * plate_quantity if need_plate else 0),
        "summa_dkp": "0",
    }


def create_paid_order(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    need_plate: bool = False,
    plate_quantity: int = 1,
) -> dict:
    create_response = client.post(
        "/orders",
        json=make_order_payload(need_plate=need_plate, plate_quantity=plate_quantity),
        headers=auth_headers,
    )
    assert create_response.status_code == 200, create_response.text
    order = create_response.json()

    pay_response = client.post(f"/orders/{order['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text
    return order


def test_analytics_dashboard_returns_operational_sections(client: TestClient, auth_headers: dict[str, str]):
    client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "100"}, headers=auth_headers)
    client.post("/cash/shifts", json={"pavilion": 2, "opening_balance": "50"}, headers=auth_headers)

    order = create_paid_order(client, auth_headers, need_plate=True)
    extra_response = client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": "700"},
        headers=auth_headers,
    )
    assert extra_response.status_code == 200, extra_response.text

    response = client.get("/analytics/dashboard?period=month&kind=all", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["overview"]["orders_count"] == 1
    assert as_float(data["overview"]["income_total"]) == 2900.0
    assert as_float(data["overview"]["turnover_total"]) == 3400.0
    assert as_float(data["overview"]["docs_income"]) == 550.0
    assert as_float(data["overview"]["plates_income"]) == 1500.0
    assert as_float(data["overview"]["plate_extra_income"]) == 700.0
    assert as_float(data["overview"]["state_duty_total"]) == 500.0
    assert as_float(data["overview"]["state_duty_cash_total"]) == 650.0
    assert as_float(data["overview"]["state_duty_commission_income"]) == 150.0

    assert len(data["monthly_trend"]) == 12
    assert len(data["quarter_summary"]) == 4
    assert data["employee_stats"][0]["employee_name"] == "Тестовый админ"
    assert data["top_services"][0]["label"] in {"Изготовление номера", "Доплата за номера", "Заявление"}


def test_analytics_dashboard_supports_docs_and_plates_scopes(client: TestClient, auth_headers: dict[str, str]):
    client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "100"}, headers=auth_headers)
    client.post("/cash/shifts", json={"pavilion": 2, "opening_balance": "50"}, headers=auth_headers)

    order = create_paid_order(client, auth_headers, need_plate=True)
    client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": "300"},
        headers=auth_headers,
    )
    insurance_response = client.post(
        "/cash/rows",
        json={"client_name": "Страховка", "insurance": "5000", "total": "5000"},
        headers=auth_headers,
    )
    assert insurance_response.status_code == 200, insurance_response.text

    docs_response = client.get("/analytics/dashboard?period=month&kind=docs", headers=auth_headers)
    assert docs_response.status_code == 200, docs_response.text
    docs_data = docs_response.json()
    docs = docs_data["overview"]
    assert as_float(docs["income_total"]) == 1700.0
    assert as_float(docs["turnover_total"]) == 6200.0
    assert as_float(docs["plates_income"]) == 0.0
    assert as_float(docs["plate_extra_income"]) == 0.0
    assert as_float(docs["state_duty_total"]) == 500.0
    assert as_float(docs["state_duty_cash_total"]) == 650.0
    assert as_float(docs["state_duty_commission_income"]) == 150.0
    assert as_float(docs["insurance_commission_income"]) == 1000.0
    assert docs["numbers_orders_count"] == 0
    assert {row["label"] for row in docs_data["top_services"]} == {"Заявление", "Комиссия госпошлины", "Комиссия страховок"}
    insurance_employee = next(row for row in docs_data["employee_stats"] if row["employee_name"] == "Комиссия страховок")
    assert insurance_employee["orders_count"] == 1
    assert as_float(insurance_employee["income_total"]) == 1000.0
    assert as_float(sum(Decimal(str(row["income_total"])) for row in docs_data["employee_stats"])) == 1700.0

    plates_response = client.get("/analytics/dashboard?period=month&kind=plates", headers=auth_headers)
    assert plates_response.status_code == 200, plates_response.text
    plates_data = plates_response.json()
    plates = plates_data["overview"]
    assert as_float(plates["income_total"]) == 1800.0
    assert as_float(plates["docs_income"]) == 0.0
    assert as_float(plates["state_duty_total"]) == 0.0
    assert as_float(plates["state_duty_cash_total"]) == 0.0
    assert as_float(plates["state_duty_commission_income"]) == 0.0
    assert as_float(plates["insurance_commission_income"]) == 0.0
    assert plates["numbers_orders_count"] == 1
    assert {row["label"] for row in plates_data["top_services"]} == {"Изготовление номера", "Доплата за номера"}


def test_plate_director_report_counts_made_stock_and_defects(client: TestClient, auth_headers: dict[str, str]):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 5}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text

    order = create_paid_order(client, auth_headers, need_plate=True, plate_quantity=2)
    in_progress_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "PLATE_IN_PROGRESS"},
        headers=auth_headers,
    )
    assert in_progress_response.status_code == 200, in_progress_response.text
    complete_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200, complete_response.text

    defect_response = client.post("/warehouse/plate-stock/defect", headers=auth_headers)
    assert defect_response.status_code == 200, defect_response.text
    cash_in_response = client.post(
        "/cash/plate-rows",
        json={"client_name": "Приход по номерам", "quantity": 0, "amount": "3000"},
        headers=auth_headers,
    )
    assert cash_in_response.status_code == 200, cash_in_response.text
    owner_expense_response = client.post(
        "/cash/plate-rows",
        json={"client_name": "Мой расход", "quantity": 0, "amount": "-500"},
        headers=auth_headers,
    )
    assert owner_expense_response.status_code == 200, owner_expense_response.text

    report_response = client.get("/analytics/plate-report?period=month", headers=auth_headers)
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["made_quantity"] == 2
    assert as_float(report["unit_price"]) == 1500.0
    assert as_float(report["gross_amount"]) == 3000.0
    assert as_float(report["owner_expenses"]) == 500.0
    assert as_float(report["plate_cash_balance"]) == 2500.0
    assert report["defects_count"] == 1
    assert report["stock_quantity"] == 2
    assert report["reserved_quantity"] == 0
    assert report["available_quantity"] == 2

    close_response = client.post("/analytics/plate-report/close?period=month", headers=auth_headers)
    assert close_response.status_code == 200, close_response.text
    closed_report = close_response.json()["report"]
    assert as_float(closed_report["owner_expenses"]) == 500.0
    assert as_float(closed_report["plate_cash_balance"]) == 0.0


def test_plate_director_report_replaces_overlapping_close_rows(client: TestClient, auth_headers: dict[str, str]):
    today = date.today()
    start_date = today.replace(day=1)
    next_month = start_date.replace(year=start_date.year + 1, month=1) if start_date.month == 12 else start_date.replace(month=start_date.month + 1)
    end_date = next_month - timedelta(days=1)
    month_start = start_date.isoformat()
    current_day = today.isoformat()
    month_end = end_date.isoformat()
    cash_in_response = client.post(
        "/cash/plate-rows",
        json={"client_name": "Приход по номерам", "quantity": 0, "amount": "3000"},
        headers=auth_headers,
    )
    assert cash_in_response.status_code == 200, cash_in_response.text

    first_close = client.post(
        f"/analytics/plate-report/close?date_from={month_start}&date_to={current_day}",
        headers=auth_headers,
    )
    assert first_close.status_code == 200, first_close.text
    assert as_float(first_close.json()["close_amount"]) == -3000.0

    second_close = client.post(
        f"/analytics/plate-report/close?date_from={month_start}&date_to={month_end}",
        headers=auth_headers,
    )
    assert second_close.status_code == 200, second_close.text
    data = second_close.json()
    assert as_float(data["close_amount"]) == -3000.0
    assert as_float(data["report"]["plate_cash_balance"]) == 0.0

    repeat_close = client.post(
        f"/analytics/plate-report/close?date_from={month_start}&date_to={month_end}",
        headers=auth_headers,
    )
    assert repeat_close.status_code == 200, repeat_close.text
    assert as_float(repeat_close.json()["close_amount"]) == -3000.0
    assert as_float(repeat_close.json()["report"]["plate_cash_balance"]) == 0.0


def test_analytics_ignores_extra_payments_for_problem_orders(client: TestClient, auth_headers: dict[str, str]):
    client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "100"}, headers=auth_headers)
    client.post("/cash/shifts", json={"pavilion": 2, "opening_balance": "50"}, headers=auth_headers)

    order = create_paid_order(client, auth_headers, need_plate=True)
    extra_response = client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": "300"},
        headers=auth_headers,
    )
    assert extra_response.status_code == 200, extra_response.text

    before_response = client.get("/analytics/dashboard?period=month&kind=plates", headers=auth_headers)
    assert before_response.status_code == 200, before_response.text
    assert as_float(before_response.json()["overview"]["plate_extra_income"]) == 300.0

    problem_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "PROBLEM"},
        headers=auth_headers,
    )
    assert problem_response.status_code == 200, problem_response.text

    after_response = client.get("/analytics/dashboard?period=month&kind=all", headers=auth_headers)
    assert after_response.status_code == 200, after_response.text
    overview = after_response.json()["overview"]
    assert overview["orders_count"] == 0
    assert as_float(overview["plate_extra_income"]) == 0.0
    assert as_float(overview["turnover_total"]) == 0.0


def test_analytics_export_returns_csv(client: TestClient, auth_headers: dict[str, str]):
    order = create_paid_order(client, auth_headers, need_plate=True)
    client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": "300"},
        headers=auth_headers,
    )

    response = client.get("/analytics/export?format=csv&period=month&kind=all", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert "Раздел,Показатель,Значение" in body
    assert "Сводка,orders_count,1" in body
    assert "Сотрудники" in body
    assert "Динамика по месяцам" in body
