import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, ClassVar, Dict, List, Literal, Tuple
from zoneinfo import ZoneInfo

import inflect
from fastapi import Depends, FastAPI, Query, Request
from icecream import ic
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.alias_generators import to_camel, to_pascal
from sqlalchemy import (
    Column,
    MetaData,
    Table,
    create_engine,
    func,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.automap import AutomapBase, automap_base
from sqlalchemy.orm import DeclarativeBase, DeclarativeMeta

from .config import logger as _logger
from .config import settings

engine = create_async_engine(
    f"postgresql+asyncpg://{settings.pg_user}:{settings.pg_password}@"
    f"{settings.pg_host}:"
    f"{'5432'}/{settings.pg_database}",
    echo=settings.echo_sql,
    pool_pre_ping=True,
)


async def get_async_session():
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


models_registry: Dict[str, BaseModel] = {}
Base: AutomapBase = None


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"

inflect_eng = inflect.engine()
inflect_eng.classical(names=0)

def pydantic_field_from_column(column: Column) -> Tuple[Any, Field]:
    ic(column)
    ic(column.type.python_type)
    return (column.type.python_type, Field(None, description=column.comment))


def introspect():
    # Introspection is only supported for sync engines
    _engine = create_engine(
        f"postgresql+psycopg://{settings.pg_user}:{settings.pg_password}@"
        f"{settings.pg_host}:"
        f"{'5432'}/{settings.pg_database}",
        echo=settings.echo_sql,
        pool_pre_ping=True,
    )
    metadata = MetaData()
    metadata.reflect(bind=_engine, schema=settings.pg_app_schema)
    global Base
    Base = automap_base(metadata=metadata)
    # calling prepare() just sets up mapped classes and relationships.
    Base.prepare()
    for table in metadata.sorted_tables:
        field_dict: dict[str, Tuple[Any, Field]] = {
            k: pydantic_field_from_column(v) for k, v in table.columns.items()
        }
        model: BaseModel = create_model(
            to_pascal(inflect_eng.singular_noun(table.name)),
            __config__=ConfigDict(from_attributes=True),
            # __cls_kwargs__={"table": True, "__tablename__": table.name},
            **field_dict,
        )
        models_registry[table.name] = model

def create_endpoint(orm_class: DeclarativeMeta, endpoint_type: str):
    endpoint = {}
    if endpoint_type == "list":
        async def endpoint(
            request: Request,
            filter_query: Annotated[FilterParams, Query()] = None,
            session: AsyncSession = Depends(get_async_session),
        ):
            role = "fras.marco"
            await session.execute(text(f"SET ROLE '{role}'"))
            statement = select(orm_class)
            results = (await session.execute(statement)).scalars().all()
            return results
    if endpoint_type == "get_one":
        async def endpoint(
            request: Request,
            id: uuid.UUID,
            session: AsyncSession = Depends(get_async_session),
        ):
            role = "fras.marco"
            await session.execute(text(f"SET ROLE '{role}'"))            
            return await session.get(orm_class, id)
    return endpoint



def add_routes(app: FastAPI):
    introspect()
    for key, model in models_registry.items():
        orm_class : DeclarativeMeta = Base.classes.get(key)
        table: Table = orm_class.__table__
        # list
        app.add_api_route(
            f"/api/{inflect_eng.plural_noun(key.lower())}",
            create_endpoint(Base.classes.get(key), "list"),
            response_model=List[model],
            # dependencies= [Depends(get_session)],
            methods=["GET"],
            tags=[key],
        )
        # get one by pk
        pks = table.primary_key.columns.keys()
        '/'.join([f'{{{pk}}}' for pk in pks])
        app.add_api_route(
            f"/api/{inflect_eng.singular_noun(key.lower())}/{"/".join([f"{{{pk}}}" for pk in pks])}",
            create_endpoint(Base.classes.get(key), "get_one"),
            response_model=model,
            methods=["GET"],
            tags=[key],
        )