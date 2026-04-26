"""Критические сценарии авторизации, заказа и оплаты."""

from fastapi.testclient import TestClient


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


def test_deactivated_user_token_is_rejected(client: TestClient, auth_headers: dict[str, str]):
    created = client.post(
        "/employees",
        json={
            "name": "Временный оператор",
            "role": "ROLE_OPERATOR",
            "login": "temporary",
            "password": "temporary123",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text

    login_response = client.post("/auth/login", data={"username": "temporary", "password": "temporary123"})
    assert login_response.status_code == 200, login_response.text
    temporary_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    deleted = client.delete(f"/employees/{created.json()['id']}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text

    me_response = client.get("/auth/me", headers=temporary_headers)
    assert me_response.status_code == 401, me_response.text


def test_login_is_rate_limited_after_repeated_failures(client: TestClient):
    for _ in range(5):
        response = client.post("/auth/login", data={"username": "missing-user", "password": "wrong-password"})
        assert response.status_code == 401, response.text

    blocked = client.post("/auth/login", data={"username": "missing-user", "password": "wrong-password"})
    assert blocked.status_code == 429, blocked.text


def test_payment_flow_creates_payments_and_cash_row(client: TestClient, auth_headers: dict[str, str]):
    order = create_paid_order(client, auth_headers, need_plate=True)

    payments_response = client.get(f"/orders/{order['id']}/payments", headers=auth_headers)
    assert payments_response.status_code == 200, payments_response.text
    payments = payments_response.json()
    assert payments["total_paid"] == 2700.0
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
    assert first_row["state_duty"] == 650.0
    assert first_row["plates"] == 1500.0
    assert first_row["total"] == 2700.0

    detail_response = client.get(f"/orders/{order['id']}/detail", headers=auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "PAID"

    repeat_pay_response = client.post(f"/orders/{order['id']}/pay", headers=auth_headers)
    assert repeat_pay_response.status_code == 409, repeat_pay_response.text
    repeat_payments = client.get(f"/orders/{order['id']}/payments", headers=auth_headers).json()
    assert repeat_payments["total_paid"] == 2700.0


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


def test_order_payment_creates_workday_cash_bucket_automatically(client: TestClient, auth_headers: dict[str, str]):
    create_response = client.post("/orders", json=make_order_payload(), headers=auth_headers)
    assert create_response.status_code == 200, create_response.text

    pay_response = client.post(f"/orders/{create_response.json()['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text

    current_response = client.get("/cash/shifts/current", params={"pavilion": 1}, headers=auth_headers)
    assert current_response.status_code == 200, current_response.text
    current_data = current_response.json()
    assert current_data["shift"]["status"] == "OPEN"
    assert current_data["total_in_shift"] == 1200.0

    day_response = client.get("/cash/days/current", params={"pavilion": 1}, headers=auth_headers)
    assert day_response.status_code == 200, day_response.text
    assert day_response.json()["program_total"] == 1200.0
    assert day_response.json()["status"] == "not_reconciled"

    reconcile_response = client.post(
        "/cash/days/reconcile",
        json={"pavilion": 1, "actual_balance": "1000", "note": "Недостача 200"},
        headers=auth_headers,
    )
    assert reconcile_response.status_code == 200, reconcile_response.text
    reconciled = reconcile_response.json()
    assert reconciled["status"] == "difference"
    assert reconciled["difference"] == -200.0


def test_state_duty_settings_and_commission_withdrawal(client: TestClient, auth_headers: dict[str, str]):
    settings_response = client.get("/settings/state-duty", headers=auth_headers)
    assert settings_response.status_code == 200, settings_response.text
    assert settings_response.json()["commission"] == 150.0
    assert settings_response.json()["special_2025_cash_amount"] == 2200.0

    updated_response = client.put(
        "/settings/state-duty",
        json={"commission": "200", "special_2025_cash_amount": "2250"},
        headers=auth_headers,
    )
    assert updated_response.status_code == 200, updated_response.text
    assert updated_response.json()["commission"] == 200.0
    assert updated_response.json()["special_2025_cash_amount"] == 2250.0

    create_response = client.post(
        "/orders",
        json={**make_order_payload(), "state_duty": "2025"},
        headers=auth_headers,
    )
    assert create_response.status_code == 200, create_response.text
    order = create_response.json()
    assert float(order["total_amount"]) == 2800.0

    pay_response = client.post(f"/orders/{order['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text

    summary_response = client.get("/cash/state-duty-commissions", headers=auth_headers)
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["commission_total"] == 225.0
    assert summary["state_duty_total"] == 2250.0
    assert summary["withdrawal_total"] == 2250.0
    assert summary["can_withdraw"] is True

    withdraw_response = client.post("/cash/state-duty-commissions/withdraw", json={}, headers=auth_headers)
    assert withdraw_response.status_code == 200, withdraw_response.text
    assert withdraw_response.json()["withdrawn"] is True

    repeat_response = client.post("/cash/state-duty-commissions/withdraw", json={}, headers=auth_headers)
    assert repeat_response.status_code == 200, repeat_response.text
    assert repeat_response.json()["withdrawn"] is True
    assert repeat_response.json()["withdrawn_total"] == 2250.0
    assert repeat_response.json()["withdrawal_total"] == 0.0
    assert repeat_response.json()["can_withdraw"] is False

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    commission_rows = [
        row for row in cash_rows_response.json()
        if row["source_type"] == "STATE_DUTY_COMMISSION_WITHDRAWAL"
    ]
    assert len(commission_rows) == 1
    assert commission_rows[0]["state_duty"] == -2250.0
    assert commission_rows[0]["total"] == -2250.0

    late_order = client.post("/orders", json=make_order_payload(), headers=auth_headers)
    assert late_order.status_code == 200, late_order.text
    late_pay = client.post(f"/orders/{late_order.json()['id']}/pay", headers=auth_headers)
    assert late_pay.status_code == 200, late_pay.text

    late_summary_response = client.get("/cash/state-duty-commissions", headers=auth_headers)
    assert late_summary_response.status_code == 200, late_summary_response.text
    late_summary = late_summary_response.json()
    assert late_summary["state_duty_total"] == 2950.0
    assert late_summary["withdrawn_total"] == 2250.0
    assert late_summary["withdrawal_total"] == 700.0
    assert late_summary["can_withdraw"] is True

    late_withdraw_response = client.post("/cash/state-duty-commissions/withdraw", json={}, headers=auth_headers)
    assert late_withdraw_response.status_code == 200, late_withdraw_response.text
    assert late_withdraw_response.json()["withdrawn_total"] == 2950.0
    assert late_withdraw_response.json()["withdrawal_total"] == 0.0

    cash_rows_after_late_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_after_late_response.status_code == 200, cash_rows_after_late_response.text
    commission_rows_after_late = [
        row for row in cash_rows_after_late_response.json()
        if row["source_type"] == "STATE_DUTY_COMMISSION_WITHDRAWAL"
    ]
    assert sorted(row["state_duty"] for row in commission_rows_after_late) == [-2250.0, -700.0]


def test_state_duty_commission_summary_follows_cash_row_deletion(client: TestClient, auth_headers: dict[str, str]):
    create_paid_order(client, auth_headers)

    summary_response = client.get("/cash/state-duty-commissions", headers=auth_headers)
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["commission_total"] == 150.0
    assert summary_response.json()["state_duty_total"] == 650.0

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    state_duty_rows = [
        row for row in cash_rows_response.json()
        if row["client_name"] == "Иван Иванов" and row["state_duty"] == 650.0
    ]
    assert len(state_duty_rows) == 1

    delete_response = client.delete(f"/cash/rows/{state_duty_rows[0]['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    updated_summary_response = client.get("/cash/state-duty-commissions", headers=auth_headers)
    assert updated_summary_response.status_code == 200, updated_summary_response.text
    updated_summary = updated_summary_response.json()
    assert updated_summary["commission_total"] == 0.0
    assert updated_summary["state_duty_total"] == 0.0
    assert updated_summary["can_withdraw"] is False


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
