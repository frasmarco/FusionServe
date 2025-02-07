from functools import lru_cache
from typing import ClassVar, List, Set

import inflect
from pydantic import ConfigDict
from pydantic.alias_generators import to_snake
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declared_attr

from .config import settings

engine = create_engine(
    f"postgresql+psycopg://{settings.pg_user}:{settings.pg_password}@"
    f"{settings.pg_host}:"
    f"{'5432'}/{settings.pg_database}",
    echo=settings.echo_sql,
    pool_pre_ping=True,
)

async_engine = create_async_engine(
    f"postgresql+asyncpg://{settings.pg_user}:{settings.pg_password}@"
    f"{settings.pg_host}:"
    f"{'5432'}/{settings.pg_database}",
    echo=settings.echo_sql,
    pool_pre_ping=True,
)


async def get_async_session():
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


"""SQLModel.metadata.schema = settings.pg_app_schema


class CommonModel(SQLModel):

    _pkey: ClassVar[List[str]] = ["id"]
    _related: ClassVar[Set[str]] = set()
    _already_existing: bool = None

    @declared_attr.directive
    def __tablename__(cls) -> str:
        engine = inflect.engine()
        engine.classical(names=0)
        return to_snake(engine.plural_noun(cls.__name__))

    @classmethod
    @lru_cache(typed=True)
    def _get_table(cls):
        return Table(
            cls._get_table_name(),
            SQLModel.metadata,
            autoload_with=engine,
            include_columns=cls.model_fields,
        )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )
"""
