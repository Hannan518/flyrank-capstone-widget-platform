import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.auth import router as auth_router
from app.api.admin.widgets import router as widgets_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="flyrank-capstone-widget-platform", version="0.1.0")

settings = get_settings()

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

install_error_handlers(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(widgets_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    from sqlalchemy import text

    from app.core.db import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logging.getLogger(__name__).exception("database health check failed")
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return {"status": "ok", "database": "ok"}
