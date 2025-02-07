from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, Request, UploadFile
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY, generate_latest

from .config import settings
from .db import add_routes

_logger = logging.getLogger("uvicorn.error")
_logger.setLevel(os.environ.get("LOG_LEVEL", "ERROR"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    add_routes(app)
    yield


# uvicorn entry point
app = FastAPI(
    title=settings.app_name,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    redirect_slashes=False,
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)


@app.get("/metrics")
async def get_metrics():
    return PlainTextResponse(generate_latest())
