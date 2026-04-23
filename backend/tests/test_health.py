"""Проверка живости приложения."""
import pytest


def test_health(client):
    """GET /health возвращает 200 и status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
