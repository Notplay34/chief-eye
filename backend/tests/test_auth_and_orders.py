"""Критические сценарии авторизации, заказа и оплаты."""

from fastapi.testclient import TestClient


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


def create_paid_order(client: TestClient, auth_headers: dict[str, str], *, need_plate: bool = False, plate_quantity: int = 1) -> dict:
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


def test_login_returns_token(client: TestClient):
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin1234"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["name"] == "Тестовый админ"
    assert data["user"]["role"] == "ROLE_ADMIN"
    assert data["access_token"]


def test_me_requires_auth(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)


def test_me_with_token_returns_current_user(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Тестовый админ"
    assert data["role"] == "ROLE_ADMIN"
    assert sorted(data["allowed_pavilions"]) == [1, 2]
    assert len(data["menu_items"]) > 0


def test_payment_flow_creates_payments_and_cash_row(client: TestClient, auth_headers: dict[str, str]):
    client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "100"}, headers=auth_headers)
    client.post("/cash/shifts", json={"pavilion": 2, "opening_balance": "50"}, headers=auth_headers)

    order = create_paid_order(client, auth_headers, need_plate=True)

    payments_response = client.get(f"/orders/{order['id']}/payments", headers=auth_headers)
    assert payments_response.status_code == 200, payments_response.text
    payments = payments_response.json()
    assert payments["total_paid"] == 2550.0
    assert payments["debt"] == 0.0
    assert sorted(payment["type"] for payment in payments["payments"]) == [
        "INCOME_PAVILION1",
        "STATE_DUTY",
    ]

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    first_row = cash_rows_response.json()[0]
    assert first_row["client_name"] == "Иван Иванов"
    assert first_row["application"] == 550.0
    assert first_row["state_duty"] == 500.0
    assert first_row["plates"] == 1500.0
    assert first_row["total"] == 2550.0

    detail_response = client.get(f"/orders/{order['id']}/detail", headers=auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "PAID"


def test_order_author_is_taken_from_jwt_not_payload(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/orders",
        json={**make_order_payload(), "employee_id": 999999},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    detail_response = client.get(f"/orders/{response.json()['id']}/detail", headers=auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["created_by_name"] == "Тестовый админ"


def test_order_payment_requires_open_shift(client: TestClient, auth_headers: dict[str, str]):
    create_response = client.post("/orders", json=make_order_payload(), headers=auth_headers)
    assert create_response.status_code == 200, create_response.text

    pay_response = client.post(f"/orders/{create_response.json()['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 400, pay_response.text
    assert "откройте смену" in pay_response.json()["detail"].lower()


def test_empty_order_is_rejected(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/orders",
        json={
            "client_fio": "Иван Иванов",
            "brand_model": "Lada Vesta",
            "state_duty": "0",
            "need_plate": False,
            "documents": [],
            "summa_dkp": "0",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text
    assert "хотя бы один документ" in response.json()["detail"].lower()
