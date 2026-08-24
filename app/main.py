import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.db import engine

logger = logging.getLogger(__name__)

app = FastAPI(title="flyrank-capstone-widget-platform", version="0.1.0")


@app.get("/health")
async def health() -> JSONResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
