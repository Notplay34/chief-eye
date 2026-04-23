"""Критические сценарии по сменам, складу и выплатам за номера."""

from fastapi.testclient import TestClient


def make_plate_order_payload(*, plate_quantity: int = 1) -> dict:
    return {
        "client_fio": "Пётр Петров",
        "brand_model": "Kia Rio",
        "state_duty": "500",
        "need_plate": True,
        "plate_quantity": plate_quantity,
        "documents": [
            {"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"},
            {"template": "number.docx", "label": "Номера", "price": "2000"},
        ],
        "extra_amount": "0",
        "plate_amount": "0",
        "summa_dkp": "0",
    }


def create_paid_plate_order(client: TestClient, auth_headers: dict[str, str], *, plate_quantity: int = 1) -> dict:
    create_response = client.post("/orders", json=make_plate_order_payload(plate_quantity=plate_quantity), headers=auth_headers)
    assert create_response.status_code == 200, create_response.text
    order = create_response.json()

    pay_response = client.post(f"/orders/{order['id']}/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text
    return order


def test_cash_shift_lifecycle_tracks_total_in_shift(client: TestClient, auth_headers: dict[str, str]):
    open_response = client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "100"}, headers=auth_headers)
    assert open_response.status_code == 200, open_response.text

    create_paid_plate_order(client, auth_headers)

    current_response = client.get("/cash/shifts/current", params={"pavilion": 1}, headers=auth_headers)
    assert current_response.status_code == 200, current_response.text
    current_data = current_response.json()
    assert current_data["shift"]["status"] == "OPEN"
    assert current_data["total_in_shift"] == 2550.0

    close_response = client.patch(
        f"/cash/shifts/{current_data['shift']['id']}/close",
        json={"closing_balance": "1600"},
        headers=auth_headers,
    )
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "CLOSED"

    list_response = client.get("/cash/shifts", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()[0]["status"] == "CLOSED"


def test_plate_status_flow_updates_stock_and_payout_register(client: TestClient, auth_headers: dict[str, str]):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 5}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text
    assert add_stock_response.json()["quantity"] == 5

    order = create_paid_plate_order(client, auth_headers, plate_quantity=2)

    in_progress_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "PLATE_IN_PROGRESS"},
        headers=auth_headers,
    )
    assert in_progress_response.status_code == 200, in_progress_response.text

    stock_response = client.get("/warehouse/plate-stock", headers=auth_headers)
    assert stock_response.status_code == 200, stock_response.text
    stock_data = stock_response.json()
    assert stock_data["quantity"] == 5
    assert stock_data["reserved"] == 2
    assert stock_data["available"] == 3

    extra_payment_response = client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": 700},
        headers=auth_headers,
    )
    assert extra_payment_response.status_code == 200, extra_payment_response.text

    complete_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200, complete_response.text

    final_stock_response = client.get("/warehouse/plate-stock", headers=auth_headers)
    final_stock = final_stock_response.json()
    assert final_stock["quantity"] == 3
    assert final_stock["reserved"] == 0
    assert final_stock["available"] == 3

    payouts_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_response.status_code == 200, payouts_response.text
    payouts = payouts_response.json()
    assert payouts["total"] == 2200.0
    assert payouts["rows"][0]["client_name"] == "Пётр Петров"


def test_paying_plate_payouts_moves_money_between_cash_tables(client: TestClient, auth_headers: dict[str, str]):
    client.post("/warehouse/plate-stock/add", json={"amount": 3}, headers=auth_headers)

    order = create_paid_plate_order(client, auth_headers)

    client.patch(f"/orders/{order['id']}/status", json={"status": "PLATE_IN_PROGRESS"}, headers=auth_headers)
    client.patch(f"/orders/{order['id']}/status", json={"status": "COMPLETED"}, headers=auth_headers)

    pay_payouts_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert pay_payouts_response.status_code == 200, pay_payouts_response.text
    assert pay_payouts_response.json()["count"] == 1
    assert pay_payouts_response.json()["total"] == 1500.0

    open_payouts_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert open_payouts_response.status_code == 200, open_payouts_response.text
    assert open_payouts_response.json()["rows"] == []
    assert open_payouts_response.json()["total"] == 0.0

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 1500.0
    assert plate_rows_response.json()["rows"][0]["client_name"] == "Пётр Петров"

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    payout_rows = [row for row in cash_rows_response.json() if row["client_name"] == "Номера — выдача"]
    assert len(payout_rows) == 1
    assert payout_rows[0]["plates"] == -1500.0
    assert payout_rows[0]["total"] == -1500.0


def test_plate_extra_payment_uses_workday_cash_bucket_automatically(client: TestClient, auth_headers: dict[str, str]):
    order = create_paid_plate_order(client, auth_headers)

    extra_payment_response = client.post(
        f"/orders/{order['id']}/pay-extra",
        json={"amount": 700},
        headers=auth_headers,
    )
    assert extra_payment_response.status_code == 200, extra_payment_response.text

    current_response = client.get("/cash/shifts/current", params={"pavilion": 2}, headers=auth_headers)
    assert current_response.status_code == 200, current_response.text
    assert current_response.json()["shift"]["status"] == "OPEN"
