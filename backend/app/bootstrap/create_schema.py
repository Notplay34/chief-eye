"""Create missing database tables from SQLAlchemy metadata.

This command is used by server setup before Alembic so a fresh database has the
base tables that legacy idempotent migrations expect.
"""

import asyncio

from app import models  # noqa: F401 - register all models on Base metadata
from app.core.database import Base, engine
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def create_missing_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    logger.info("Базовая схема БД проверена/создана")


def main() -> None:
    asyncio.run(create_missing_schema())


if __name__ == "__main__":
    main()
