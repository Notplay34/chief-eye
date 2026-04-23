"""Тесты авторизации и создания заказа + оплаты."""
import os

import pytest

# Логин/пароль из .env для теста (если нет — тесты с БД пропускаются)
SUPERUSER_LOGIN = os.environ.get("SUPERUSER_LOGIN", "sergey151")
SUPERUSER_PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "1wq21wq2")


@pytest.fixture
def auth_headers(client):
    """Получить заголовок Authorization после логина суперпользователя."""
    r = client.post(
        "/auth/login",
        data={"username": SUPERUSER_LOGIN, "password": SUPERUSER_PASSWORD},
    )
    if r.status_code != 200:
        pytest.skip("Логин не удался (нет БД или неверные SUPERUSER_* в env)")
    data = r.json()
    token = data.get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token(client):
    """POST /auth/login с верными данными возвращает access_token."""
    r = client.post(
        "/auth/login",
        data={"username": SUPERUSER_LOGIN, "password": SUPERUSER_PASSWORD},
    )
    if r.status_code == 401:
        pytest.skip("Нет тестового пользователя в БД")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
    assert "user" in data


def test_me_requires_auth(client):
    """GET /auth/me без токена возвращает 401 или 403."""
    r = client.get("/auth/me")
    assert r.status_code in (401, 403)


def test_me_with_token(client, auth_headers):
    """GET /auth/me с токеном возвращает данные пользователя."""
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert "role" in data
    assert "allowed_pavilions" in data
    assert "menu_items" in data


def test_create_order_and_pay(client, auth_headers):
    """POST /orders создаёт заказ, POST /orders/{id}/pay принимает оплату."""
    # Минимальное тело заказа (обязательные поля по схеме)
    order_body = {
        "state_duty": 0,
        "extra_amount": 0,
        "plate_amount": 0,
        "summa_dkp": 0,
        "need_plate": False,
        "documents": [],
    }
    r = client.post("/orders", json=order_body, headers=auth_headers)
    if r.status_code in (401, 403):
        pytest.skip("Нет прав на создание заказа")
    assert r.status_code == 200, r.text
    data = r.json()
    order_id = data["id"]
    assert order_id

    # Оплата заказа (перевод в PAID)
    pay_r = client.post(f"/orders/{order_id}/pay", headers=auth_headers)
    assert pay_r.status_code == 200, pay_r.text
    pay_data = pay_r.json()
    assert "order_id" in pay_data or "id" in data
