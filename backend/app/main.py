"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import api_router

app = FastAPI(
    title="Football Intelligence API",
    description="Professional football analytics and prediction platform",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Football Intelligence API",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Football Intelligence API",
        "version": "0.1.0",
        "docs": "/docs",
    }
