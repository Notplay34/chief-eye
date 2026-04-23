"""Фикстуры для тестов API."""
import os

import pytest
from fastapi.testclient import TestClient

# Использовать тестовую БД, если задана (чтобы не трогать прод)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def client():
    """Тестовый клиент приложения."""
    from app.main import app
    return TestClient(app)
