import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> Iterator[None]:
    database_path = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        poolclass=NullPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    asyncio.run(create_schema())
    app.dependency_overrides[get_db_session] = override_session
    yield
    app.dependency_overrides.pop(get_db_session, None)
    asyncio.run(engine.dispose())
