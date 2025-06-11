from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings

engine = create_async_engine(url=settings.DATABASE_URL, echo=True)


async def init_db():
    # from . import models

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(text('PRAGMA foreign_keys=ON'))  # for SQLite only


async def get_session():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
    async with async_session() as session:  # type: ignore
        try:
            yield session
        finally:
            await session.close()
