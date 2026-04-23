"""Initial data bootstrap helpers."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.identity import normalize_login
from app.core.logging_config import get_logger
from app.data.price_list import PRICE_LIST as DEFAULT_PRICE_LIST
from app.models import DocumentPrice, Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import hash_password
from app.services.template_registry import supported_sellable_templates

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
    login = normalize_login(settings.superuser_login)

    async with session_maker() as session:
        result = await session.execute(select(Employee).where(Employee.login_normalized == login))
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
        supported_templates = supported_sellable_templates()
        if supported_templates:
            await session.execute(
                delete(DocumentPrice).where(DocumentPrice.template.notin_(supported_templates))
            )

        result = await session.execute(select(DocumentPrice))
        existing = {row.template: row for row in result.scalars().all()}

        for index, item in enumerate(DEFAULT_PRICE_LIST):
            if item["template"] not in supported_templates:
                continue
            row = existing.get(item["template"])
            if row is None:
                session.add(
                    DocumentPrice(
                        template=item["template"],
                        label=item["label"],
                        price=item["price"],
                        sort_order=index,
                    )
                )
        await session.commit()
        logger.info("Прейскурант синхронизирован с доступными шаблонами")
