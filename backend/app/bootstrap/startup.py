"""Application startup orchestration."""

from app import models  # noqa: F401 - ensure models are registered on Base metadata
from app.bootstrap.schema import ensure_schema_compatibility
from app.bootstrap.seed import ensure_superuser, seed_document_prices
from app.config import settings
from app.core.database import Base, async_session_maker, engine
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def run_startup_tasks() -> None:
    """Create base schema and run idempotent startup tasks."""
    if settings.generated_jwt_secret:
        logger.warning(
            "JWT_SECRET не задан: используется временный секрет для %s. В production задайте JWT_SECRET явно.",
            settings.app_env,
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы БД проверены/созданы")

    tasks = (
        ("Миграция схемы", ensure_schema_compatibility(engine)),
        ("Суперпользователь", ensure_superuser(async_session_maker)),
        ("Прейскурант", seed_document_prices(async_session_maker)),
    )
    for label, coro in tasks:
        try:
            await coro
        except Exception as exc:
            logger.warning("%s: %s", label, exc)


async def shutdown_resources() -> None:
    """Release shared infrastructure resources on shutdown."""
    await engine.dispose()
