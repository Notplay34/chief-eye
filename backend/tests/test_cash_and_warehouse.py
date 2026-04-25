"""Критические сценарии по сменам, складу и выплатам за номера."""

from datetime import date

from fastapi.testclient import TestClient


def make_plate_order_payload(*, plate_quantity: int = 1) -> dict:
    return {
        "client_fio": "Петров Пётр Петрович",
        "brand_model": "Kia Rio",
        "state_duty": "500",
        "need_plate": True,
        "plate_quantity": plate_quantity,
        "documents": [
            {"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"},
        ],
        "extra_amount": "0",
        "plate_amount": str(1500 * plate_quantity),
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
    assert current_data["total_in_shift"] == 2700.0

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
    assert payouts["total"] == 3700.0
    assert payouts["rows"][0]["client_name"] == "Петров Пётр Петрович"


def test_intermediate_plate_money_is_payable_only_after_client_issue(client: TestClient, auth_headers: dict[str, str]):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 2}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text

    order = create_paid_plate_order(client, auth_headers, plate_quantity=2)

    payouts_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_response.status_code == 200, payouts_response.text
    payouts = payouts_response.json()
    assert payouts["total"] == 3000.0
    assert payouts["quantity"] == 2
    assert payouts["rows"][0]["client_name"] == "Петров Пётр Петрович"

    pay_payouts_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert pay_payouts_response.status_code == 200, pay_payouts_response.text
    assert pay_payouts_response.json()["count"] == 1
    assert pay_payouts_response.json()["total"] == 3000.0

    transfer_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfer_response.status_code == 200, transfer_response.text
    assert transfer_response.json()["total"] == 0.0
    assert transfer_response.json()["rows"] == []

    blocked_pay_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert blocked_pay_response.status_code == 400, blocked_pay_response.text

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

    transfer_after_issue_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfer_after_issue_response.status_code == 200, transfer_after_issue_response.text
    assert transfer_after_issue_response.json()["total"] == 3000.0
    assert transfer_after_issue_response.json()["quantity"] == 2

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["rows"] == []


def test_deleting_paid_order_cash_row_rolls_back_related_cash_and_analytics(client: TestClient, auth_headers: dict[str, str]):
    order = create_paid_plate_order(client, auth_headers)

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    cash_row = next(row for row in cash_rows_response.json() if row["source_batch"] == str(order["id"]))

    payouts_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_response.status_code == 200, payouts_response.text
    assert payouts_response.json()["total"] == 1500.0

    analytics_response = client.get("/analytics/dashboard?period=month", headers=auth_headers)
    assert analytics_response.status_code == 200, analytics_response.text
    assert analytics_response.json()["overview"]["orders_count"] == 1

    delete_response = client.delete(f"/cash/rows/{cash_row['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    payouts_after_delete = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_after_delete.status_code == 200, payouts_after_delete.text
    assert payouts_after_delete.json()["total"] == 0.0
    assert payouts_after_delete.json()["rows"] == []

    payments_response = client.get(f"/orders/{order['id']}/payments", headers=auth_headers)
    assert payments_response.status_code == 200, payments_response.text
    assert payments_response.json()["total_paid"] == 0

    detail_response = client.get(f"/orders/{order['id']}/detail", headers=auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "AWAITING_PAYMENT"

    analytics_after_delete = client.get("/analytics/dashboard?period=month", headers=auth_headers)
    assert analytics_after_delete.status_code == 200, analytics_after_delete.text
    assert analytics_after_delete.json()["overview"]["orders_count"] == 0
    assert float(analytics_after_delete.json()["overview"]["turnover_total"]) == 0.0


def test_deleting_paid_order_cash_row_removes_transferred_plate_cash_rows(client: TestClient, auth_headers: dict[str, str]):
    stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 3}, headers=auth_headers)
    assert stock_response.status_code == 200, stock_response.text

    order = create_paid_plate_order(client, auth_headers)
    cash_row = next(
        row for row in client.get("/cash/rows", headers=auth_headers).json()
        if row["source_batch"] == str(order["id"])
    )
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
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 2

    transfer_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert transfer_response.status_code == 200, transfer_response.text

    pay_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 1500.0

    delete_response = client.delete(f"/cash/rows/{cash_row['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    plate_rows_after_delete = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_after_delete.status_code == 200, plate_rows_after_delete.text
    assert plate_rows_after_delete.json()["total"] == 0
    assert plate_rows_after_delete.json()["rows"] == []

    transfers_after_delete = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_after_delete.status_code == 200, transfers_after_delete.text
    assert transfers_after_delete.json()["total"] == 0.0
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 3


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

    transfer_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfer_response.status_code == 200, transfer_response.text
    assert transfer_response.json()["total"] == 1500.0
    assert transfer_response.json()["rows"][0]["client_short_name"] == "Петров П.П."
    assert transfer_response.json()["rows"][0]["quantity"] == 1

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 0.0
    assert plate_rows_response.json()["rows"] == []

    cash_rows_response = client.get("/cash/rows", headers=auth_headers)
    assert cash_rows_response.status_code == 200, cash_rows_response.text
    payout_rows = [
        row
        for row in cash_rows_response.json()
        if row["client_name"] == "Петров П.П." and row["plates"] == -1500.0
    ]
    assert len(payout_rows) == 1
    assert payout_rows[0]["plates"] == -1500.0
    assert payout_rows[0]["total"] == -1500.0

    pay_transfers_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_transfers_response.status_code == 200, pay_transfers_response.text
    assert pay_transfers_response.json()["count"] == 1
    assert pay_transfers_response.json()["total"] == 1500.0

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 1500.0
    assert plate_rows_response.json()["rows"][0]["client_name"] == "Петров П.П."

    delete_response = client.delete(f"/cash/rows/{payout_rows[0]['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    plate_rows_after_delete_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_after_delete_response.status_code == 200, plate_rows_after_delete_response.text
    assert plate_rows_after_delete_response.json()["rows"] == []
    assert plate_rows_after_delete_response.json()["total"] == 0.0

    open_payouts_after_delete_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert open_payouts_after_delete_response.status_code == 200, open_payouts_after_delete_response.text
    assert open_payouts_after_delete_response.json()["total"] == 1500.0


def test_manual_plate_cash_row_quantity_adjusts_stock_and_amount(client: TestClient, auth_headers: dict[str, str]):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 5}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text

    create_response = client.post(
        "/cash/plate-rows",
        json={"client_name": "Ручная продажа", "quantity": 2, "amount": 1},
        headers=auth_headers,
    )
    assert create_response.status_code == 200, create_response.text
    row = create_response.json()
    assert row["quantity"] == 2
    assert row["amount"] == 3000.0
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 3

    update_response = client.patch(
        f"/cash/plate-rows/{row['id']}",
        json={"quantity": 3},
        headers=auth_headers,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["quantity"] == 3
    assert update_response.json()["amount"] == 4500.0
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 2

    failed_update_response = client.patch(
        f"/cash/plate-rows/{row['id']}",
        json={"quantity": 6},
        headers=auth_headers,
    )
    assert failed_update_response.status_code == 400, failed_update_response.text
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 2

    zero_response = client.patch(
        f"/cash/plate-rows/{row['id']}",
        json={"quantity": 0, "amount": 777},
        headers=auth_headers,
    )
    assert zero_response.status_code == 200, zero_response.text
    assert zero_response.json()["quantity"] == 0
    assert zero_response.json()["amount"] == 777.0
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 5


def test_warehouse_monthly_history_tracks_incoming_made_and_defects(client: TestClient, auth_headers: dict[str, str]):
    current_month = date.today().strftime("%Y-%m")

    assert client.post("/warehouse/plate-stock/add", json={"amount": 10}, headers=auth_headers).status_code == 200
    sale_response = client.post(
        "/cash/plate-rows",
        json={"client_name": "История", "quantity": 2},
        headers=auth_headers,
    )
    assert sale_response.status_code == 200, sale_response.text
    assert client.post("/warehouse/plate-stock/defect", headers=auth_headers).status_code == 200

    monthly_response = client.get(
        "/warehouse/plate-stock/monthly",
        params={"month_from": current_month, "month_to": current_month},
        headers=auth_headers,
    )
    assert monthly_response.status_code == 200, monthly_response.text
    row = monthly_response.json()["rows"][0]
    assert row["month"] == current_month
    assert row["opening_balance"] == 0
    assert row["incoming"] == 10
    assert row["made"] == 2
    assert row["defects"] == 1
    assert row["closing_balance"] == 7

    movements_response = client.get(
        "/warehouse/plate-stock/movements",
        params={"month_from": current_month, "month_to": current_month},
        headers=auth_headers,
    )
    assert movements_response.status_code == 200, movements_response.text
    movement_types = [row["movement_type"] for row in movements_response.json()["rows"]]
    assert {"STOCK_IN", "PLATE_CASH_SALE", "DEFECT"} <= set(movement_types)


def test_cash_rows_can_be_filtered_by_business_date(client: TestClient, auth_headers: dict[str, str]):
    create_paid_plate_order(client, auth_headers)

    all_cash_response = client.get("/cash/rows", headers=auth_headers)
    assert all_cash_response.status_code == 200, all_cash_response.text
    assert len(all_cash_response.json()) >= 1

    today_response = client.get("/cash/rows", params={"business_date": date.today().isoformat()}, headers=auth_headers)
    assert today_response.status_code == 200, today_response.text
    assert len(today_response.json()) >= 1

    old_response = client.get("/cash/rows", params={"business_date": "2020-01-01"}, headers=auth_headers)
    assert old_response.status_code == 200, old_response.text
    assert old_response.json() == []


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
