import asyncio
from enum import Enum
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, ClassVar, Dict, List, Literal, Set, Tuple
from zoneinfo import ZoneInfo

import inflect as _inflect
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


class RegistryItem(BaseModel):
    model: Any = None
    get_input: Any = None
    create_input: Any = None


class PaginationParams(BaseModel):
    limit: int = Field(100, alias="__limit",gt=0, le=settings.max_page_lenght)
    offset: int = Field(0, alias="__offset", ge=0)
    order_by: str | None = Field(None, alias="__order_by")

models_registry: Dict[str, RegistryItem] = {}
Base: AutomapBase = None
inflect = _inflect.engine()
inflect.classical(names=0)


def pydantic_field_from_column(
    column: Column, model_type: Literal["model", "get_input", "create_input"]
) -> Tuple[Any, Field]:
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        python_type = str
    field_type = {
        "model": python_type | None if column.nullable else python_type,
        "get_input": python_type | None,
        "create_input": python_type | None if not column.primary_key else python_type,
    }[model_type]
    return (field_type, Field(None, description=column.comment))


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
        if not inflect.singular_noun(table.name):
            raise ValueError(f"Table name {table.name} is not plural")
        item = RegistryItem()
        for model_type in RegistryItem.model_fields.keys():
            setattr(
                item,
                model_type,
                create_model(
                    to_pascal(f"{inflect.singular_noun(table.name)}_{model_type}"),
                    __config__=ConfigDict(from_attributes=True),
                    **{
                        k: pydantic_field_from_column(v, model_type)
                        for k, v in table.columns.items()
                    },
                ),
            )
        models_registry[table.name] = item


def create_endpoint(table_name: str, endpoint_type: str):
    endpoint = {}
    orm_class : DeclarativeMeta = Base.classes.get(table_name)
    if endpoint_type == "list":
        get_input = models_registry[table_name].get_input
        async def endpoint(
            # request: Request,
            basic_filter: Annotated[get_input, Query(), Depends()], # type: ignore
            pagination: Annotated[PaginationParams, Query(), Depends()] = None,
            session: AsyncSession = Depends(get_async_session),
        ):
            # TODO: role from jwt or anonymous
            role = "fras.marco"
            await session.execute(text(f"SET ROLE '{role}'"))
            statement = (
                select(orm_class).limit(pagination.limit).offset(pagination.offset)
            )
            for k in basic_filter.model_fields:
                # skip attributes not in query string
                if getattr(basic_filter, k):
                    #print(getattr(basic_filter, k))
                    # add the where condition to select expression
                    statement = statement.where(getattr(orm_class, k) == getattr(basic_filter, k))
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
    for key, item in models_registry.items():
        table: Table = Base.classes.get(key).__table__
        # list
        app.add_api_route(
            f"/api/{key.lower()}",
            create_endpoint(key, "list"),
            response_model=List[item.model],
            #dependencies=[Annotated[Depends(item.get_input), Query()]],
            summary=f"List all {key}",
            operation_id=f"get_all_{key}",
            methods=["GET"],
            tags=[key],
        )
        # get one by pk
        # TODO: returning a single object, include related records
        pks = table.primary_key.columns.keys()
        "/".join([f"{{{pk}}}" for pk in pks])
        app.add_api_route(
            f"/api/{key.lower()}/{"/".join([f"{{{pk}}}" for pk in pks])}",
            create_endpoint(key, "get_one"),
            response_model=item.model,
            summary=f"Get one {inflect.singular_noun(key)} by primary key",
            operation_id=f"get_one_{inflect.singular_noun(key)}",
            methods=["GET"],
            tags=[key],
        )
        # The POST method is used for creating data
        # The PUT replace completely the resource
        # the PATCH method is used for partially updating a resource
        # The DELETE method is used for removing data.
        # http://api.example.com/v1/store/items/{id}✅
        # http://api.example.com/v1/store/employees/{id}✅
        # http://api.example.com/v1/store/employees/{id}/addresses
        # /device-management/managed-devices/{id}/scripts/{id}/execute	//DON't DO THIS!
        # /device-management/managed-devices/{id}/scripts/{id}/status		//POST request with action=execute
        # $ protects keywords in pagination and advanced filtering
        # /api/books?$offset=0&$limit=10&$orderBy=author desc,title asc
        # basic FILTER on equality of fields
        # http://api.example.com/v1/store/items?group=124
        # http://api.example.com/v1/store/employees?department=IT&region=USA
        # advanced FILTER on multiple fields using expressions
        # /api/books?page=0&size=20&$filter=author eq 'Fitzgerald'
        # /api/books?page=0&size=20&$filter=(author eq 'Fitzgerald' or name eq 'Redmond') and price lt 2.55
        # /v1.0/people?$filter=name eq 'david'&$orderBy=hireDate
        # https://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#_Toc31361038
