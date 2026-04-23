"""Initial data bootstrap helpers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.logging_config import get_logger
from app.data.price_list import PRICE_LIST as DEFAULT_PRICE_LIST
from app.models import DocumentPrice, Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import hash_password

logger = get_logger(__name__)


async def ensure_superuser(session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Create the initial superuser if it does not exist yet."""
    if settings.has_partial_superuser_config:
        logger.warning(
            "Суперпользователь не создан: нужно задать все SUPERUSER_LOGIN, SUPERUSER_PASSWORD и SUPERUSER_NAME"
        )
        return

    if not settings.should_create_superuser:
        return
    login = (settings.superuser_login or "").strip()

    async with session_maker() as session:
        result = await session.execute(select(Employee).where(Employee.login == login))
        if result.scalar_one_or_none() is not None:
            return

        password = settings.superuser_password or ""
        name = (settings.superuser_name or login).strip()
        session.add(
            Employee(
                name=name,
                role=EmployeeRole.ROLE_ADMIN,
                login=login,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        await session.commit()
        logger.info("Создан суперпользователь: %s", login)


async def seed_document_prices(session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Seed default document prices if the table is empty."""
    async with session_maker() as session:
        result = await session.execute(select(DocumentPrice).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        for index, item in enumerate(DEFAULT_PRICE_LIST):
            session.add(
                DocumentPrice(
                    template=item["template"],
                    label=item["label"],
                    price=item["price"],
                    sort_order=index,
                )
            )
        await session.commit()
        logger.info("Прейскурант заполнен из дефолтного списка (%s позиций)", len(DEFAULT_PRICE_LIST))
