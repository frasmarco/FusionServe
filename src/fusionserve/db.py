import asyncio
import inspect
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, ClassVar, Dict, List
from zoneinfo import ZoneInfo

import inflect
from fastapi import Depends, FastAPI, Request
from icecream import ic
from pydantic import create_model
from pydantic.alias_generators import to_camel, to_pascal
from sqlalchemy import MetaData, func, insert, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Column, FetchedValue, Field, Session, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ._common_model import async_engine, engine
from .config import logger as _logger
from .config import settings
from .models import Job


def get_session():
    with Session(engine) as session:
        yield session


MODEL_REGISTRY: Dict[str, SQLModel] = {}


async def introspect():
    with Session(engine) as session:
        metadata = MetaData()
        metadata.reflect(bind=engine, schema=settings.pg_app_schema)
        inflect_eng = inflect.engine()
        inflect_eng.classical(names=0)
        for table in reversed(metadata.sorted_tables):
            field_dict: Dict[str, (Any, Field)] = {
                "id": (
                    uuid.UUID,
                    Field(
                        default=None,
                        sa_column=Column(
                            UUID, primary_key=True, server_default=FetchedValue()
                        ),
                    ),
                )
            }
            model: SQLModel = create_model(
                to_pascal(inflect_eng.singular_noun(table.name)),
                __base__=SQLModel,
                __cls_kwargs__={"table": True, "__tablename__": table.name},
                __tablename__=(ClassVar[str], table.name),
                **field_dict,
            )
            ic(model.__tablename__)
            MODEL_REGISTRY[table.name] = model


def create_endpoint(model: SQLModel):
    async def endpoint(request: Request, session: Session = Depends(get_session)):
        # ic(session)
        # ic(request)
        # ic(model)
        statement = select(model)
        results = session.exec(statement)
        return results

    return endpoint


async def add_routes(app: FastAPI):
    await introspect()
    for key, value in MODEL_REGISTRY.items():
        app.add_api_route(
            f"/api/{key.lower()}",
            create_endpoint(value),
            response_model=value,
            # dependencies= [Depends(get_session)],
            methods=["GET"],
        )
