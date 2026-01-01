"""Universe service REST API application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.universe.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Universe Service",
    description="Security universe management service",
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
app.include_router(router, prefix="/universe", tags=["universe"])


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Universe service starting up...")
    logger.info("Service ready on port 8001")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Universe service shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # nosec B104
        port=8001,
        reload=True,
        log_level="info",
    )
