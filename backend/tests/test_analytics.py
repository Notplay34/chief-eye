"""Базовые сценарии аналитики."""

from decimal import Decimal

from fastapi.testclient import TestClient


def as_float(value) -> float:
    return float(Decimal(str(value)))


def make_order_payload(*, need_plate: bool = False, plate_quantity: int = 1) -> dict:
    documents = [
        {"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"},
    ]
    if need_plate:
        documents.append({"template": "number.docx", "label": "Номера", "price": "2000"})
    return {
        "client_fio": "Иван Иванов",
        "brand_model": "Lada Vesta",
        "state_duty": "500",
        "need_plate": need_plate,
        "plate_quantity": plate_quantity,
        "documents": documents,
        "extra_amount": "0",
        "plate_amount": "0",
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
    assert as_float(data["overview"]["income_total"]) == 2750.0
    assert as_float(data["overview"]["turnover_total"]) == 3250.0
    assert as_float(data["overview"]["docs_income"]) == 550.0
    assert as_float(data["overview"]["plates_income"]) == 1500.0
    assert as_float(data["overview"]["plate_extra_income"]) == 700.0
    assert as_float(data["overview"]["state_duty_total"]) == 500.0

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

    docs_response = client.get("/analytics/dashboard?period=month&kind=docs", headers=auth_headers)
    assert docs_response.status_code == 200, docs_response.text
    docs = docs_response.json()["overview"]
    assert as_float(docs["income_total"]) == 550.0
    assert as_float(docs["plates_income"]) == 0.0
    assert as_float(docs["plate_extra_income"]) == 0.0
    assert as_float(docs["state_duty_total"]) == 500.0

    plates_response = client.get("/analytics/dashboard?period=month&kind=plates", headers=auth_headers)
    assert plates_response.status_code == 200, plates_response.text
    plates = plates_response.json()["overview"]
    assert as_float(plates["income_total"]) == 1800.0
    assert as_float(plates["docs_income"]) == 0.0
    assert as_float(plates["state_duty_total"]) == 0.0
    assert plates["numbers_orders_count"] == 1


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
