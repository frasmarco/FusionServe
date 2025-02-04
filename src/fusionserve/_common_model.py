from functools import lru_cache
from typing import ClassVar, List, Set

import inflect
from pydantic import ConfigDict
from pydantic.alias_generators import to_snake
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declared_attr
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

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

from sqlalchemy import event

@event.listens_for(engine, 'before_cursor_execute')
#@event.listens_for(async_engine, 'before_cursor_execute')
def do_set_role(conn, cursor, statement, parameters, context, executemany):
    "listen for the 'before_cursor_execute' event"
    cursor.execute("SET ROLE 'fras.marco'")

async def get_async_session():
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


SQLModel.metadata.schema = settings.pg_app_schema


class CommonModel(SQLModel):
    """
    A common base model that provides basic CRUD operations for database tables.

    Attributes:
        _pkey (List[str]): List of primary key fields.
        _related (Set[str]): Set of related fields.
        _already_existing (bool): Flag to check if the record already exists.
    """

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
        """
        Retrieves the table associated with the model,
        creating it based on the class name.

        Returns:
            Table: A SQLAlchemy Table object representing the model's table in the db.
        """
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
