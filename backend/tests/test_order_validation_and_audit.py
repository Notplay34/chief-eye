"""Validation, audit and plate-only access regressions."""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AuditLog, Order


def make_base_payload() -> dict:
    return {
        "client_fio": "Иванов Иван Иванович",
        "client_passport": "1814 123456",
        "client_address": "г. Волгоград, ул. Ленина, д. 10",
        "client_phone": "+7 (999) 123-45-67",
        "brand_model": "Lada Vesta",
        "vehicle_type": "Легковой",
        "year": "2021",
        "vin": "XTA217230N0000001",
        "engine": "1.6",
        "chassis": "отсутствует",
        "body": "XTA217230N0000001",
        "color": "Белый",
        "srts": "99AA123456",
        "plate_number": "A001AA34",
        "pts": "78УУ123456",
        "state_duty": "500",
        "summa_dkp": "850000",
        "dkp_date": "23.04.2026",
        "seller_fio": "Петров Пётр Петрович",
        "seller_passport": "1814 654321",
        "seller_address": "г. Михайловка, ул. Советская, д. 5",
        "trustee_fio": "Сидоров Сидор Сидорович",
        "trustee_passport": "1814 777777",
        "trustee_basis": "доверенность № 42",
    }


def test_create_order_rejects_invalid_inn_ogrn_plate_and_year(client: TestClient, auth_headers: dict[str, str]):
    invalid_cases = [
        ("client_inn", "12345", "инн"),
        ("client_ogrn", "123", "огрн"),
        ("plate_number", "12", "госномер"),
        ("year", "20AB", "год"),
    ]

    for field, value, expected in invalid_cases:
        payload = make_base_payload()
        payload["documents"] = [{"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"}]
        payload[field] = value
        response = client.post("/orders", json=payload, headers=auth_headers)
        assert response.status_code == 422, response.text
        assert expected in str(response.json()["detail"]).lower()


def test_create_order_accepts_split_documents_and_relaxed_vin(client: TestClient, auth_headers: dict[str, str]):
    payload = make_base_payload()
    payload.update(
        {
            "client_passport": None,
            "client_passport_series": "1814",
            "client_passport_number": "123456",
            "client_passport_issued_by": "ГУ МВД России",
            "client_passport_issued_date": "01.02.2020",
            "client_passport_division_code": "340001",
            "srts": None,
            "srts_series": "99AA",
            "srts_number": "123456",
            "pts": None,
            "pts_series": "78УУ",
            "pts_number": "123456",
            "vin": "abcioq1",
            "documents": [{"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"}],
        }
    )

    response = client.post("/orders", json=payload, headers=auth_headers)

    assert response.status_code == 200, response.text
    detail = client.get(f"/orders/{response.json()['id']}/detail", headers=auth_headers).json()
    assert detail["form_data"]["client_passport"] == "1814 123456"
    assert detail["form_data"]["client_passport_division_code"] == "340-001"
    assert detail["form_data"]["srts"] == "99AA 123456"
    assert detail["form_data"]["pts"] == "78УУ 123456"
    assert detail["form_data"]["vin"] == "ABCIOQ1"


def test_create_order_rejects_missing_required_fields_for_selected_templates(client: TestClient, auth_headers: dict[str, str]):
    payload = make_base_payload()
    payload["documents"] = [{"template": "DKP.docx", "label": "ДКП", "price": "550"}]
    payload["seller_passport"] = None

    response = client.post("/orders", json=payload, headers=auth_headers)

    assert response.status_code == 400, response.text
    assert "паспорт продавца" in response.json()["detail"].lower()


def test_document_print_rejects_missing_required_fields(client: TestClient, auth_headers: dict[str, str], db_session):
    payload = make_base_payload()
    payload["documents"] = [{"template": "zaiavlenie.docx", "label": "Заявление", "price": "550"}]
    create_response = client.post("/orders", json=payload, headers=auth_headers)
    assert create_response.status_code == 200, create_response.text
    order_id = create_response.json()["id"]

    order = asyncio.run(db_session.execute(select(Order).where(Order.id == order_id))).scalar_one()
    order.form_data = {**(order.form_data or {}), "vin": None}
    db_session.add(order)
    asyncio.run(db_session.commit())

    response = client.get(f"/orders/{order_id}/documents/zaiavlenie.docx", headers=auth_headers)
    assert response.status_code == 400, response.text
    assert "не хватает данных" in response.json()["detail"].lower()


def test_audit_log_records_key_actions(client: TestClient, auth_headers: dict[str, str]):
    payload = make_base_payload()
    payload["need_plate"] = True
    payload["plate_quantity"] = 1
    payload["documents"] = [
        {"template": "zaiavlenie.docx", "label": "Заявление", "price": "550"},
        {"template": "number.docx", "label": "Номера", "price": "1500"},
    ]
    create_response = client.post("/orders", json=payload, headers=auth_headers)
    assert create_response.status_code == 200, create_response.text
    order_id = create_response.json()["id"]

    assert client.post(f"/orders/{order_id}/pay", headers=auth_headers).status_code == 200
    assert client.post("/warehouse/plate-stock/add", json={"amount": 3}, headers=auth_headers).status_code == 200
    assert client.patch(f"/orders/{order_id}/status", json={"status": "PLATE_IN_PROGRESS"}, headers=auth_headers).status_code == 200
    assert client.patch(f"/orders/{order_id}/status", json={"status": "COMPLETED"}, headers=auth_headers).status_code == 200
    assert client.post("/cash/plate-payouts/pay", headers=auth_headers).status_code == 200

    logs_response = client.get("/audit/logs", headers=auth_headers)
    assert logs_response.status_code == 200, logs_response.text
    event_types = {row["event_type"] for row in logs_response.json()}
    assert {"order_created", "order_paid", "plate_payout_created", "order_status_changed", "plate_payouts_paid"} <= event_types


def test_plate_operator_is_forced_to_plate_only_contour(client: TestClient, auth_headers: dict[str, str]):
    create_employee = client.post(
        "/employees",
        json={"name": "Номерщик", "role": "ROLE_PLATE_OPERATOR", "login": "plate", "password": "plate123"},
        headers=auth_headers,
    )
    assert create_employee.status_code == 200, create_employee.text

    plate_login = client.post("/auth/login", data={"username": "plate", "password": "plate123"})
    assert plate_login.status_code == 200, plate_login.text
    plate_headers = {"Authorization": f"Bearer {plate_login.json()['access_token']}"}

    payload = make_base_payload()
    payload["need_plate"] = True
    payload["plate_quantity"] = 1
    payload["documents"] = [
        {"template": "zaiavlenie.docx", "label": "Заявление", "price": "550"},
        {"template": "number.docx", "label": "Номера", "price": "1500"},
    ]
    create_response = client.post("/orders", json=payload, headers=auth_headers)
    assert create_response.status_code == 200, create_response.text
    order_id = create_response.json()["id"]

    assert client.get("/orders", headers=plate_headers).status_code == 403
    assert client.get(f"/orders/{order_id}", headers=plate_headers).status_code == 403
    assert client.get(f"/orders/{order_id}/payments", headers=plate_headers).status_code == 403

    plate_detail = client.get(f"/orders/plate/{order_id}", headers=plate_headers)
    assert plate_detail.status_code == 200, plate_detail.text
    payload = plate_detail.json()
    assert set(payload.keys()) == {"id", "public_id", "status", "client", "brand_model", "plate_amount", "debt", "plate_document", "created_at"}
