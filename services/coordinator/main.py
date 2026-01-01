"""Coordinator Service - FastAPI application."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.coordinator.routes import router

app = FastAPI(
    title="Coordinator Service",
    description="Orchestrates planning workflow across microservices",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/coordinator", tags=["coordinator"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "coordinator",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8011,
        reload=True,
    )
