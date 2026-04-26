"""Smoke-проверки ролей и базового access matrix."""

from fastapi.testclient import TestClient


def create_employee(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    role: str,
    login: str,
    password: str,
) -> dict:
    response = client.post(
        "/employees",
        json={
            "name": name,
            "role": role,
            "login": login,
            "password": password,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def login_headers(client: TestClient, login: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": login, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def menu_ids(me_payload: dict) -> set[str]:
    return {item["id"] for item in me_payload["menu_items"]}


def test_role_smoke_matrix(client: TestClient, auth_headers: dict[str, str]):
    create_employee(
        client,
        auth_headers,
        name="Менеджер",
        role="ROLE_MANAGER",
        login="manager",
        password="manager123",
    )
    create_employee(
        client,
        auth_headers,
        name="Оператор",
        role="ROLE_OPERATOR",
        login="operator",
        password="operator123",
    )
    create_employee(
        client,
        auth_headers,
        name="Номерщик",
        role="ROLE_PLATE_OPERATOR",
        login="plate",
        password="plate123",
    )

    admin = auth_headers
    manager = login_headers(client, "manager", "manager123")
    operator = login_headers(client, "operator", "operator123")
    plate = login_headers(client, "plate", "plate123")

    admin_me = client.get("/auth/me", headers=admin)
    manager_me = client.get("/auth/me", headers=manager)
    operator_me = client.get("/auth/me", headers=operator)
    plate_me = client.get("/auth/me", headers=plate)

    assert admin_me.status_code == 200, admin_me.text
    assert manager_me.status_code == 200, manager_me.text
    assert operator_me.status_code == 200, operator_me.text
    assert plate_me.status_code == 200, plate_me.text

    admin_menu = menu_ids(admin_me.json())
    manager_menu = menu_ids(manager_me.json())
    operator_menu = menu_ids(operator_me.json())
    plate_menu = menu_ids(plate_me.json())

    assert {"analytics_docs", "analytics_plates", "plate_report", "admin", "users"} <= admin_menu
    assert "analytics_docs" not in manager_menu
    assert {"form_p1", "plates", "plate_cash", "warehouse", "cash_p1", "plate_transfer"} <= manager_menu
    assert {"form_p1", "cash_p1", "plate_transfer"} <= operator_menu
    assert {"plates", "plate_cash", "warehouse"} <= plate_menu
    assert "form_p1" not in plate_menu

    assert manager_me.json()["allowed_pavilions"] == [1, 2]
    assert operator_me.json()["allowed_pavilions"] == [1]
    assert plate_me.json()["allowed_pavilions"] == [2]

    assert client.get("/analytics/dashboard?period=month", headers=admin).status_code == 200
    assert client.get("/analytics/dashboard?period=month", headers=manager).status_code == 403
    assert client.get("/analytics/dashboard?period=month", headers=operator).status_code == 403
    assert client.get("/analytics/dashboard?period=month", headers=plate).status_code == 403

    for headers in (admin, manager, operator):
        assert client.post(
            "/cash/rows",
            json={"client_name": "Касса 1", "application": "100", "total": "100"},
            headers=headers,
        ).status_code == 200

    cash_row = client.post(
        "/cash/rows",
        json={"client_name": "Закрытая строка", "application": "50", "total": "50"},
        headers=admin,
    )
    assert cash_row.status_code == 200, cash_row.text
    cash_row_id = cash_row.json()["id"]

    assert client.get("/cash/rows", headers=plate).status_code == 403
    assert client.post(
        "/cash/rows",
        json={"client_name": "Чужая касса", "application": "1", "total": "1"},
        headers=plate,
    ).status_code == 403
    assert client.patch(
        f"/cash/rows/{cash_row_id}",
        json={"client_name": "Чужое изменение"},
        headers=plate,
    ).status_code == 403
    assert client.delete(f"/cash/rows/{cash_row_id}", headers=plate).status_code == 403
    assert client.get("/cash/plate-payouts", headers=plate).status_code == 403
    assert client.post("/cash/plate-payouts/pay", headers=plate).status_code == 403
    assert client.get("/cash/plate-transfers", headers=plate).status_code == 403
    assert client.post("/cash/plate-transfers/pay", headers=plate).status_code == 403
    assert client.get("/cash/plate-rows", headers=plate).status_code == 200

    assert client.post("/cash/shifts", json={"pavilion": 1, "opening_balance": "0"}, headers=admin).status_code == 200
    assert client.post("/cash/shifts", json={"pavilion": 2, "opening_balance": "0"}, headers=plate).status_code == 200
    assert client.get("/cash/shifts", params={"pavilion": 1}, headers=plate).status_code == 403
    plate_shifts_p2 = client.get("/cash/shifts", params={"pavilion": 2}, headers=plate)
    assert plate_shifts_p2.status_code == 200, plate_shifts_p2.text
    assert {shift["pavilion"] for shift in plate_shifts_p2.json()} == {2}
    plate_shifts_all = client.get("/cash/shifts", headers=plate)
    assert plate_shifts_all.status_code == 200, plate_shifts_all.text
    assert {shift["pavilion"] for shift in plate_shifts_all.json()} == {2}

    operator_order = client.post(
        "/orders",
        json={
            "client_fio": "Тест Клиент",
            "brand_model": "Lada Vesta",
            "state_duty": "500",
            "need_plate": False,
            "documents": [{"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"}],
            "extra_amount": "0",
            "plate_amount": "0",
            "summa_dkp": "0",
        },
        headers=operator,
    )
    assert operator_order.status_code == 200, operator_order.text
    assert client.post(
        "/orders",
        json={
            "client_fio": "Павильон 2",
            "brand_model": "Lada Vesta",
            "state_duty": "500",
            "need_plate": False,
            "documents": [{"template": "zaiavlenie.docx", "label": "Заявление", "price": "1000"}],
            "extra_amount": "0",
            "plate_amount": "0",
            "summa_dkp": "0",
        },
        headers=plate,
    ).status_code == 403

    assert client.get("/warehouse/plate-stock", headers=plate).status_code == 200
    assert client.get("/warehouse/plate-stock", headers=operator).status_code == 403
    assert client.get(f"/orders/{operator_order.json()['id']}", headers=plate).status_code == 403
    assert client.get(
        f"/orders/{operator_order.json()['id']}/documents/zaiavlenie.docx",
        headers=plate,
    ).status_code == 403
    assert client.get("/employees?all=true", headers=admin).status_code == 200
    assert client.get("/employees?all=true", headers=manager).status_code == 200
    assert client.post(
        "/employees",
        json={"name": "Лишний", "role": "ROLE_OPERATOR", "login": "x1", "password": "x1234"},
        headers=manager,
    ).status_code == 403


def test_employee_login_is_normalized_and_unique(client: TestClient, auth_headers: dict[str, str]):
    first = client.post(
        "/employees",
        json={"name": "Admin 2", "role": "ROLE_OPERATOR", "login": "  MiXeD  ", "password": "test1234"},
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["login"] == "mixed"

    duplicate = client.post(
        "/employees",
        json={"name": "Admin 3", "role": "ROLE_OPERATOR", "login": "mixed", "password": "test1234"},
        headers=auth_headers,
    )
    assert duplicate.status_code == 400, duplicate.text
    assert "занят" in duplicate.json()["detail"].lower()

    login_response = client.post("/auth/login", data={"username": "  MIXED ", "password": "test1234"})
    assert login_response.status_code == 200, login_response.text
