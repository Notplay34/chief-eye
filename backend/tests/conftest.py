"""Фикстуры для изолированных API-тестов."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.data.price_list import PRICE_LIST
from app.models import DocumentPrice, Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import hash_password
from app.services.template_registry import supported_sellable_templates

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin1234"
ADMIN_NAME = "Тестовый админ"


def _run(coro):
    return asyncio.run(coro)


async def _prepare_database(database_url: str) -> tuple:
    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        session.add(
            Employee(
                name=ADMIN_NAME,
                role=EmployeeRole.ROLE_ADMIN,
                login=ADMIN_LOGIN,
                password_hash=hash_password(ADMIN_PASSWORD),
                is_active=True,
            )
        )
        supported_templates = supported_sellable_templates()
        for index, item in enumerate(PRICE_LIST):
            if item["template"] not in supported_templates:
                continue
            session.add(
                DocumentPrice(
                    template=item["template"],
                    label=item["label"],
                    price=item["price"],
                    sort_order=index,
                )
            )
        await session.commit()

    return engine, session_maker


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тестовый клиент приложения с отдельной SQLite-БД на каждый тест."""
    database_path = tmp_path / "test.sqlite3"
    engine, session_maker = _run(_prepare_database(f"sqlite+aiosqlite:///{database_path}"))

    import app.main as main_module

    async def _noop() -> None:
        return None

    monkeypatch.setattr(main_module, "run_startup_tasks", _noop)
    monkeypatch.setattr(main_module, "shutdown_resources", _noop)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    _run(engine.dispose())


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Authorization header для тестового администратора."""
    response = client.post(
        "/auth/login",
        data={"username": ADMIN_LOGIN, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
