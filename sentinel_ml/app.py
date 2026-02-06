"""Sentinel ML micro-service FastAPI app."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel_ml.api.routers import analytics_router, jobs_router, ml_router
from sentinel_ml.api.routers.jobs import set_scheduler
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MLDatabase
from sentinel_ml.jobs import init as init_jobs
from sentinel_ml.jobs import stop as stop_jobs
from sentinel_ml.ml_monitor import MLMonitor
from sentinel_ml.ml_retrainer import MLRetrainer
from sentinel_ml.regime_hmm import RegimeDetector
from sentinel_ml.version import VERSION

logger = logging.getLogger(__name__)

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler

    ml_db = MLDatabase()
    await ml_db.connect()

    monolith = MonolithDataClient()
    detector = RegimeDetector()
    retrainer = MLRetrainer(ml_db=ml_db)
    monitor = MLMonitor(ml_db=ml_db)

    _scheduler = await init_jobs(ml_db, monolith, detector, retrainer, monitor)
    set_scheduler(_scheduler)
    logger.info("ML scheduler started")

    yield

    await stop_jobs()
    await ml_db.close()


app = FastAPI(
    title="Sentinel ML",
    description="Dedicated ML micro-service for Sentinel",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "sentinel-ml"}


@app.get("/version")
async def version() -> dict[str, str]:
    return {"version": VERSION}


app.include_router(ml_router)
app.include_router(analytics_router)
app.include_router(jobs_router)
