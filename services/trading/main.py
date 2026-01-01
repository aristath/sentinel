"""Trading service REST API application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.trading.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Trading Service",
    description="Trade execution service",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router, prefix="/trading", tags=["trading"])


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Trading service starting up...")
    logger.info("Service ready on port 8003")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Trading service shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # nosec B104
        port=8003,
        reload=True,
        log_level="info",
    )
