from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, crawl_logs, data_sources, settings, videos, webhooks
from app.core.database import init_db
from app.services.scheduler import scheduler_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await scheduler_service.start()
    try:
        yield
    finally:
        await scheduler_service.stop()


app = FastAPI(
    title="TradingRader API",
    description="Financial data source feed aggregation service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(data_sources.router, prefix="/api/data-sources", tags=["data-sources"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(crawl_logs.router, prefix="/api/crawl-logs", tags=["crawl-logs"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
