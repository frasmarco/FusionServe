# from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, FetchedValue, Field

from ._common_model import CommonModel


class Job(CommonModel, table=True):
    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID, primary_key=True, server_default=FetchedValue()),
    )
    external_id: Optional[str] = None
    cluster: Optional[str] = None
    queue: Optional[str] = None
    log_timestamp: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    queued_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    exit_code: Optional[int] = None
