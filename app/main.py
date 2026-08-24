import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.admin.auth import router as auth_router
from app.api.admin.widgets import router as widgets_router
from app.api.public.submissions import router as public_router
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import install_error_handlers
from app.jobs.outbox_worker import OutboxWorker, Pruner
from app.services.geo.factory import build_geo_chain
from app.services.mailers import build_mailer

logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    app.state.geo_chain = build_geo_chain(settings)
    mailer = build_mailer(settings.email_mode)
    worker = OutboxWorker(
        session_factory,
        mailer,
        poll_interval_seconds=settings.jobs_poll_interval_seconds,
    )
    pruner = Pruner(
        session_factory,
        interval_seconds=60.0,
        rate_limit_retention_seconds=settings.rate_limit_retention_seconds,
        job_retention_days=settings.job_retention_days,
    )
    tasks = [
        asyncio.create_task(worker.run_forever(), name="outbox-worker"),
        asyncio.create_task(pruner.run_forever(), name="pruner"),
    ]
    logging.getLogger(__name__).info("background jobs started")
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await app.state.geo_chain.aclose()
    logging.getLogger(__name__).info("background jobs stopped")


app = FastAPI(
    title="flyrank-capstone-widget-platform", version="0.1.0", lifespan=lifespan
)

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
app.include_router(public_router, prefix="/api/v1")


@app.get("/health")
async def health() -> JSONResponse:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logging.getLogger(__name__).exception("database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
