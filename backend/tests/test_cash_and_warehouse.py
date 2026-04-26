"""Критические сценарии по сменам, складу и выплатам за номера."""

import asyncio
from decimal import Decimal
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import CashRow, Order, Payment, PlateCashRow, PlateStock
from app.services.cash_service import ORDER_PAYMENT_CASH_ROW


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


def run_async(coro):
    return asyncio.run(coro)


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
    assert stock_data["reserved_breakdown"] == [{"total_amount": 3000.0, "quantity": 2}]

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


def test_plate_stock_summary_consolidates_duplicate_stock_rows(client: TestClient, auth_headers: dict[str, str], db_session):
    async def create_duplicate_stock_rows():
        db_session.add_all([PlateStock(quantity=250), PlateStock(quantity=10)])
        await db_session.commit()

    run_async(create_duplicate_stock_rows())

    stock_response = client.get("/warehouse/plate-stock", headers=auth_headers)
    assert stock_response.status_code == 200, stock_response.text
    assert stock_response.json()["quantity"] == 260

    async def read_stock_rows():
        return (await db_session.execute(select(PlateStock).order_by(PlateStock.id))).scalars().all()

    rows = run_async(read_stock_rows())
    assert len(rows) == 1
    assert rows[0].quantity == 260


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

    transfers_before_cashier_move = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_before_cashier_move.status_code == 200, transfers_before_cashier_move.text
    assert transfers_before_cashier_move.json()["total"] == 0.0
    assert transfers_before_cashier_move.json()["rows"] == []

    blocked_before_cashier_move = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert blocked_before_cashier_move.status_code == 400, blocked_before_cashier_move.text

    pay_payouts_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert pay_payouts_response.status_code == 200, pay_payouts_response.text
    assert pay_payouts_response.json()["count"] == 1
    assert pay_payouts_response.json()["total"] == 3000.0

    transfer_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfer_response.status_code == 200, transfer_response.text
    assert transfer_response.json()["total"] == 3000.0
    assert transfer_response.json()["ready_total"] == 0.0
    assert transfer_response.json()["rows"][0]["ready_to_pay"] is False

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
    assert transfer_after_issue_response.json()["ready_total"] == 3000.0
    assert transfer_after_issue_response.json()["quantity"] == 2

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["rows"] == []

    pay_ready_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_ready_response.status_code == 200, pay_ready_response.text
    assert pay_ready_response.json()["count"] == 1
    assert pay_ready_response.json()["total"] == 3000.0

    plate_rows_after_pay_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_after_pay_response.status_code == 200, plate_rows_after_pay_response.text
    assert plate_rows_after_pay_response.json()["rows"][0]["quantity"] == 2


def test_plate_payout_transfer_uses_cash_receipt_day(client: TestClient, auth_headers: dict[str, str], db_session):
    old_day = date.today() - timedelta(days=1)
    old_datetime = datetime.combine(old_day, datetime.min.time())
    order = create_paid_plate_order(client, auth_headers, plate_quantity=2)

    async def move_cash_receipt_to_previous_day():
        cash_row = (
            await db_session.execute(
                select(CashRow).where(
                    CashRow.source_type == ORDER_PAYMENT_CASH_ROW,
                    CashRow.source_batch == str(order["id"]),
                )
            )
        ).scalar_one()
        cash_row.created_at = old_datetime

        order_row = (await db_session.execute(select(Order).where(Order.id == order["id"]))).scalar_one()
        order_row.created_at = old_datetime

        payments = (
            await db_session.execute(select(Payment).where(Payment.order_id == order["id"]))
        ).scalars().all()
        for payment in payments:
            payment.created_at = old_datetime
        await db_session.commit()

    run_async(move_cash_receipt_to_previous_day())

    today_response = client.get("/cash/plate-payouts", params={"business_date": date.today().isoformat()}, headers=auth_headers)
    assert today_response.status_code == 200, today_response.text
    assert today_response.json()["total"] == 0.0
    assert today_response.json()["rows"] == []

    old_day_response = client.get("/cash/plate-payouts", params={"business_date": old_day.isoformat()}, headers=auth_headers)
    assert old_day_response.status_code == 200, old_day_response.text
    assert old_day_response.json()["total"] == 3000.0
    assert old_day_response.json()["quantity"] == 2

    today_transfer = client.post(
        "/cash/plate-payouts/pay",
        params={"business_date": date.today().isoformat()},
        headers=auth_headers,
    )
    assert today_transfer.status_code == 400, today_transfer.text

    old_day_transfer = client.post(
        "/cash/plate-payouts/pay",
        params={"business_date": old_day.isoformat()},
        headers=auth_headers,
    )
    assert old_day_transfer.status_code == 200, old_day_transfer.text
    assert old_day_transfer.json()["total"] == 3000.0
    assert old_day_transfer.json()["business_date"] == old_day.isoformat()


def test_plate_transfer_pays_only_issued_clients_from_intermediate_cash(client: TestClient, auth_headers: dict[str, str]):
    add_stock_response = client.post("/warehouse/plate-stock/add", json={"amount": 2}, headers=auth_headers)
    assert add_stock_response.status_code == 200, add_stock_response.text

    first_order = create_paid_plate_order(client, auth_headers)
    second_order = create_paid_plate_order(client, auth_headers)

    move_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["count"] == 2
    assert move_response.json()["total"] == 3000.0

    first_progress = client.patch(
        f"/orders/{first_order['id']}/status",
        json={"status": "PLATE_IN_PROGRESS"},
        headers=auth_headers,
    )
    assert first_progress.status_code == 200, first_progress.text
    first_complete = client.patch(
        f"/orders/{first_order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert first_complete.status_code == 200, first_complete.text

    ready_transfers = client.get("/cash/plate-transfers", headers=auth_headers)
    assert ready_transfers.status_code == 200, ready_transfers.text
    assert ready_transfers.json()["total"] == 3000.0
    assert ready_transfers.json()["ready_total"] == 1500.0
    assert ready_transfers.json()["quantity"] == 2
    assert len(ready_transfers.json()["rows"]) == 2
    assert sum(1 for row in ready_transfers.json()["rows"] if row["ready_to_pay"]) == 1

    pay_ready_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_ready_response.status_code == 200, pay_ready_response.text
    assert pay_ready_response.json()["count"] == 1
    assert pay_ready_response.json()["total"] == 1500.0

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 1500.0
    assert len(plate_rows_response.json()["rows"]) == 1
    assert plate_rows_response.json()["rows"][0]["quantity"] == 1

    history_response = client.get("/cash/plate-transfers/history", headers=auth_headers)
    assert history_response.status_code == 200, history_response.text
    assert history_response.json()["total"] == 1500.0
    assert history_response.json()["rows"][0]["client_name"] == "Петров Пётр Петрович"
    assert history_response.json()["days"][0]["total"] == 1500.0
    assert history_response.json()["days"][0]["rows"][0]["client_name"] == "Петров Пётр Петрович"

    transfers_after_first_pay = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_after_first_pay.status_code == 200, transfers_after_first_pay.text
    assert transfers_after_first_pay.json()["total"] == 1500.0
    assert transfers_after_first_pay.json()["ready_total"] == 0.0
    assert len(transfers_after_first_pay.json()["rows"]) == 1

    second_progress = client.patch(
        f"/orders/{second_order['id']}/status",
        json={"status": "PLATE_IN_PROGRESS"},
        headers=auth_headers,
    )
    assert second_progress.status_code == 200, second_progress.text
    second_complete = client.patch(
        f"/orders/{second_order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert second_complete.status_code == 200, second_complete.text

    transfers_after_second_issue = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_after_second_issue.status_code == 200, transfers_after_second_issue.text
    assert transfers_after_second_issue.json()["total"] == 1500.0
    assert transfers_after_second_issue.json()["ready_total"] == 1500.0
    assert transfers_after_second_issue.json()["quantity"] == 1


def test_intermediate_cash_supports_manual_rows_and_delete(client: TestClient, auth_headers: dict[str, str]):
    create_response = client.post(
        "/cash/plate-transfers/manual",
        json={"client_name": "Ручная выдача", "quantity": 0, "amount": "1200"},
        headers=auth_headers,
    )
    assert create_response.status_code == 200, create_response.text
    row = create_response.json()
    assert row["row_type"] == "manual"
    assert row["ready_to_pay"] is True

    list_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 1200.0
    assert list_response.json()["ready_total"] == 1200.0

    delete_response = client.delete(f"/cash/plate-transfers/{row['row_key']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    after_delete = client.get("/cash/plate-transfers", headers=auth_headers)
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json()["total"] == 0.0
    assert after_delete.json()["rows"] == []


def test_manual_intermediate_row_becomes_payable_after_inline_amount(client: TestClient, auth_headers: dict[str, str]):
    create_response = client.post(
        "/cash/plate-transfers/manual",
        json={"client_name": "", "quantity": 0, "amount": 0},
        headers=auth_headers,
    )
    assert create_response.status_code == 200, create_response.text
    row = create_response.json()
    assert row["ready_to_pay"] is False

    list_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 0.0
    assert list_response.json()["ready_total"] == 0.0
    assert list_response.json()["ready_count"] == 0

    update_response = client.patch(
        f"/cash/plate-transfers/manual/{row['id']}",
        json={"client_name": "Ручная строка", "quantity": 1, "amount": "1500"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["ready_to_pay"] is True

    ready_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["total"] == 1500.0
    assert ready_response.json()["ready_total"] == 1500.0
    assert ready_response.json()["ready_count"] == 1

    pay_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text
    assert pay_response.json()["total"] == 1500.0

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    assert plate_rows_response.json()["total"] == 1500.0

    history_response = client.get("/cash/plate-transfers/history", headers=auth_headers)
    assert history_response.status_code == 200, history_response.text
    assert history_response.json()["total"] == 1500.0
    assert history_response.json()["rows"][0]["row_type"] == "manual"
    assert history_response.json()["days"][0]["rows"][0]["row_type"] == "manual"


def test_deleting_auto_intermediate_row_does_not_return_to_document_cash(client: TestClient, auth_headers: dict[str, str]):
    client.post("/warehouse/plate-stock/add", json={"amount": 1}, headers=auth_headers)
    order = create_paid_plate_order(client, auth_headers)
    move_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert move_response.status_code == 200, move_response.text

    transfers_response = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_response.status_code == 200, transfers_response.text
    row = transfers_response.json()["rows"][0]
    assert row["ready_to_pay"] is False

    delete_response = client.delete(f"/cash/plate-transfers/{row['row_key']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    after_delete = client.get("/cash/plate-transfers", headers=auth_headers)
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json()["rows"] == []

    payouts_after_delete = client.get("/cash/plate-payouts", headers=auth_headers)
    assert payouts_after_delete.status_code == 200, payouts_after_delete.text
    assert payouts_after_delete.json()["rows"] == []

    history_after_delete = client.get("/cash/plate-transfers/history", headers=auth_headers)
    assert history_after_delete.status_code == 200, history_after_delete.text
    assert history_after_delete.json()["rows"] == []

    complete_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200, complete_response.text
    assert client.get("/cash/plate-transfers", headers=auth_headers).json()["rows"] == []


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


def test_system_cash_row_allows_safe_edits_only(client: TestClient, auth_headers: dict[str, str]):
    order = create_paid_plate_order(client, auth_headers)
    cash_row = next(
        row for row in client.get("/cash/rows", headers=auth_headers).json()
        if row["source_batch"] == str(order["id"])
    )

    safe_response = client.patch(
        f"/cash/rows/{cash_row['id']}",
        json={"application": "800", "insurance": "300"},
        headers=auth_headers,
    )
    assert safe_response.status_code == 200, safe_response.text
    safe_row = safe_response.json()
    assert safe_row["application"] == 800.0
    assert safe_row["insurance"] == 300.0
    assert safe_row["total"] == (
        safe_row["application"]
        + safe_row["state_duty"]
        + safe_row["dkp"]
        + safe_row["insurance"]
        + safe_row["plates"]
    )

    for payload in ({"state_duty": "0"}, {"plates": "0"}, {"total": "0"}):
        blocked_response = client.patch(f"/cash/rows/{cash_row['id']}", json=payload, headers=auth_headers)
        assert blocked_response.status_code == 400, blocked_response.text


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
    assert plate_rows_response.json()["rows"][0]["quantity"] == 1

    delete_response = client.delete(f"/cash/rows/{payout_rows[0]['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    plate_rows_after_delete_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_after_delete_response.status_code == 200, plate_rows_after_delete_response.text
    assert plate_rows_after_delete_response.json()["rows"] == []
    assert plate_rows_after_delete_response.json()["total"] == 0.0

    open_payouts_after_delete_response = client.get("/cash/plate-payouts", headers=auth_headers)
    assert open_payouts_after_delete_response.status_code == 200, open_payouts_after_delete_response.text
    assert open_payouts_after_delete_response.json()["total"] == 1500.0


def test_plate_cash_total_uses_filtered_history_not_current_page(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session,
):
    async def create_plate_rows():
        db_session.add_all(
            [
                PlateCashRow(client_name="Строка 1", quantity=0, amount=Decimal("100")),
                PlateCashRow(client_name="Строка 2", quantity=0, amount=Decimal("200")),
                PlateCashRow(client_name="Строка 3", quantity=0, amount=Decimal("300")),
            ]
        )
        await db_session.commit()

    run_async(create_plate_rows())

    response = client.get("/cash/plate-rows", params={"limit": 2, "offset": 0}, headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["rows"]) == 2
    assert data["total"] == 600.0


def test_deleting_plate_cash_row_does_not_return_money_to_intermediate(client: TestClient, auth_headers: dict[str, str]):
    client.post("/warehouse/plate-stock/add", json={"amount": 2}, headers=auth_headers)

    order = create_paid_plate_order(client, auth_headers)
    client.patch(f"/orders/{order['id']}/status", json={"status": "PLATE_IN_PROGRESS"}, headers=auth_headers)
    client.patch(f"/orders/{order['id']}/status", json={"status": "COMPLETED"}, headers=auth_headers)

    move_response = client.post("/cash/plate-payouts/pay", headers=auth_headers)
    assert move_response.status_code == 200, move_response.text

    pay_response = client.post("/cash/plate-transfers/pay", headers=auth_headers)
    assert pay_response.status_code == 200, pay_response.text

    plate_rows_response = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_response.status_code == 200, plate_rows_response.text
    plate_row = plate_rows_response.json()["rows"][0]

    delete_response = client.delete(f"/cash/plate-rows/{plate_row['id']}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    plate_rows_after_delete = client.get("/cash/plate-rows", headers=auth_headers)
    assert plate_rows_after_delete.status_code == 200, plate_rows_after_delete.text
    assert plate_rows_after_delete.json()["rows"] == []
    assert client.get("/warehouse/plate-stock", headers=auth_headers).json()["quantity"] == 1

    transfers_after_delete = client.get("/cash/plate-transfers", headers=auth_headers)
    assert transfers_after_delete.status_code == 200, transfers_after_delete.text
    assert transfers_after_delete.json()["total"] == 0.0
    assert transfers_after_delete.json()["rows"] == []


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


def test_cash_rows_balance_ignores_selected_history_date(client: TestClient, auth_headers: dict[str, str], db_session):
    async def create_cash_rows():
        db_session.add_all([
            CashRow(client_name="День 1", total=Decimal("1000"), created_at=datetime(2026, 4, 24, 12, 0, 0)),
            CashRow(client_name="День 2", total=Decimal("500"), created_at=datetime(2026, 4, 25, 12, 0, 0)),
            CashRow(client_name="Списание", total=Decimal("-200"), created_at=datetime(2026, 4, 25, 13, 0, 0)),
        ])
        await db_session.commit()

    run_async(create_cash_rows())

    day_response = client.get("/cash/rows/balance", params={"business_date": "2026-04-25"}, headers=auth_headers)
    assert day_response.status_code == 200, day_response.text
    assert day_response.json()["balance"] == 1300.0

    previous_day_response = client.get("/cash/rows/balance", params={"business_date": "2026-04-24"}, headers=auth_headers)
    assert previous_day_response.status_code == 200, previous_day_response.text
    assert previous_day_response.json()["balance"] == 1300.0

    all_response = client.get("/cash/rows/balance", headers=auth_headers)
    assert all_response.status_code == 200, all_response.text
    assert all_response.json()["balance"] == 1300.0


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
