from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db, session_scope
from .routers.home import router as home_router
from .routers.items import router as items_router
from .routers.metrics import router as metrics_router
from .routers.logs import router as logs_router
from .routers.batches import router as batches_router
from .routers.sources import router as sources_router
from .routers.internal_crawler import router as internal_crawler_router
from .services.scheduler import start_scheduler, stop_scheduler
from .sources import ensure_sources

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(home_router)
app.include_router(items_router)
app.include_router(metrics_router)
app.include_router(logs_router)
app.include_router(batches_router)
app.include_router(sources_router)
app.include_router(internal_crawler_router)


@app.on_event("startup")
def startup_event():
    init_db()
    with session_scope() as session:
        ensure_sources(session)
    if settings.enable_scheduler:
        start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}
