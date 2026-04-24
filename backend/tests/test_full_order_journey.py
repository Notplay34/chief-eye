"""Полный сквозной сценарий: форма, оплата, документы, номера, кассы, аналитика."""

from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient


def _as_float(value) -> float:
    return float(Decimal(str(value)))


def _read_docx_xml(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as archive:
        return archive.read("word/document.xml").decode("utf-8", errors="ignore")


def make_full_order_payload() -> dict:
    return {
        "client_fio": "Иванов Иван Иванович",
        "client_passport": "1814 123456",
        "client_address": "г. Волгоград, ул. Ленина, д. 10",
        "client_phone": "+7 (999) 123-45-67",
        "client_comment": "Тестовый клиент",
        "seller_fio": "Петров Пётр Петрович",
        "seller_passport": "1814 654321",
        "seller_address": "г. Михайловка, ул. Советская, д. 5",
        "trustee_fio": "Сидоров Сидор Сидорович",
        "trustee_passport": "1814 777777",
        "trustee_basis": "доверенность № 42",
        "vin": "XTA217230N0000001",
        "brand_model": "Lada Vesta",
        "vehicle_type": "Легковой",
        "year": "2021",
        "engine": "1.6 106 л.с.",
        "chassis": "отсутствует",
        "power": "78 кВт / 106 л.с.",
        "mass": "1670 / 1235",
        "body": "XTA217230N0000001",
        "color": "Белый",
        "srts": "99AA123456",
        "plate_number": "A001AA34",
        "pts": "78УУ123456",
        "dkp_date": "23.04.2026",
        "dkp_number": "42/2026",
        "dkp_summary": "Легковой автомобиль Lada Vesta",
        "summa_dkp": "850000",
        "state_duty": "500",
        "need_plate": True,
        "plate_quantity": 2,
        "documents": [
            {"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"},
            {"template": "DKP.docx", "label": "ДКП", "price": "1500"},
            {"template": "doverennost.docx", "label": "Доверенность", "price": "1200"},
        ],
        "extra_amount": "0",
        "plate_amount": "3000",
    }


def test_full_order_journey_exercises_documents_cash_plates_and_analytics(
    client: TestClient,
    auth_headers: dict[str, str],
):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 10}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text

    create_response = client.post("/orders", json=make_full_order_payload(), headers=auth_headers)
    assert create_response.status_code == 200, create_response.text
    order = create_response.json()
    assert order["need_plate"] is True
    assert _as_float(order["total_amount"]) == 5300.0

    pay_response = client.post(f"/orders/{order['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text

    detail_response = client.get(f"/orders/{order['id']}/detail", headers=auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["form_data"]["client_phone"] == "+79991234567"
    assert detail["form_data"]["vin"] == "XTA217230N0000001"
    assert len(detail["form_data"]["documents"]) == 3

    for template_name, expected_values in {
        "zaiavlenie.docx": ["Иванов Иван Иванович", "+79991234567", "XTA217230N0000001", "78 кВт / 106 л.с.", "1670 / 1235"],
        "DKP.docx": ["Иванов Иван Иванович", "Петров Пётр Петрович", "850000"],
        "doverennost.docx": ["Иванов Иван Иванович", "Сидоров Сидор Сидорович"],
        "number.docx": ["Иванов Иван Иванович", "XTA217230N0000001"],
    }.items():
        document_response = client.get(f"/orders/{order['id']}/documents/{template_name}", headers=auth_headers)
        assert document_response.status_code == 200, document_response.text
        assert document_response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        xml = _read_docx_xml(document_response.content)
        assert "{{" not in xml
        for expected in expected_values:
            assert expected in xml

    payments_response = client.get(f"/orders/{order['id']}/payments", headers=auth_headers)
    assert payments_response.status_code == 200, payments_response.text
    payments = payments_response.json()
    assert payments["debt"] == 0.0
    assert payments["total_paid"] == 5300.0

    plate_list_response = client.get("/orders/plate-list", headers=auth_headers)
    assert plate_list_response.status_code == 200, plate_list_response.text
    assert plate_list_response.json()[0]["id"] == order["id"]

    in_progress_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "PLATE_IN_PROGRESS"},
        headers=auth_headers,
    )
    assert in_progress_response.status_code == 200, in_progress_response.text

    ready_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "PLATE_READY"},
        headers=auth_headers,
    )
    assert ready_response.status_code == 200, ready_response.text

    extra_payment_response = client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": "700"},
        headers=auth_headers,
    )
    assert extra_payment_response.status_code == 200, extra_payment_response.text

    complete_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200, complete_response.text

    payouts_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_response.status_code == 200, payouts_response.text
    payouts = payouts_response.json()
    assert payouts["rows"][0]["client_name"] == "Иванов Иван Иванович"
    assert payouts["total"] == 3700.0

    pay_payouts_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert pay_payouts_response.status_code == 200, pay_payouts_response.text
    assert pay_payouts_response.json()["total"] == 3700.0

    plate_cash_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_cash_response.status_code == 200, plate_cash_response.text
    assert plate_cash_response.json()["total"] == 3700.0

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    cash_rows = cash_rows_response.json()
    assert any(row["client_name"] == "Иванов Иван Иванович" and row["state_duty"] == 650.0 and row["total"] == 5300.0 for row in cash_rows)
    assert any(row["client_name"] == "Иванов Иван Иванович" and row["plates"] == 3000.0 for row in cash_rows)
    assert plate_cash_response.json()["rows"][0]["client_name"] == "Иванов И.И."
    assert any(row["client_name"] == "Иванов И.И." and row["plates"] == -3700.0 for row in cash_rows)

    analytics_response = client.get("/analytics/dashboard?period=month&kind=all", headers=auth_headers)
    assert analytics_response.status_code == 200, analytics_response.text
    overview = analytics_response.json()["overview"]
    assert overview["orders_count"] == 1
    assert _as_float(overview["income_total"]) == 5350.0
    assert _as_float(overview["turnover_total"]) == 5850.0
    assert _as_float(overview["docs_income"]) == 1650.0
    assert _as_float(overview["plates_income"]) == 3000.0
    assert _as_float(overview["plate_extra_income"]) == 700.0
    assert _as_float(overview["state_duty_total"]) == 500.0


def test_create_order_rejects_invalid_phone_number(client: TestClient, auth_headers: dict[str, str]):
    payload = make_full_order_payload()
    payload["client_phone"] = "+7 999 12 34"

    response = client.post("/orders", json=payload, headers=auth_headers)

    assert response.status_code == 422, response.text
    errors = response.json()["detail"]
    assert any("Телефон должен быть в формате +7XXXXXXXXXX" in str(item.get("msg", "")) for item in errors)
