"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import api_router
from app.database import get_session_factory
from app.ingestion.service import IngestionService


# Application state
class AppState:
    """Application state container."""
    ingestion_service: IngestionService = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    session_factory = get_session_factory()
    app_state.ingestion_service = IngestionService(session_factory)
    
    yield
    
    # Shutdown
    # Clean up resources if needed


app = FastAPI(
    title="Football Intelligence API",
    description="Professional football analytics and prediction platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Make app_state accessible
app.state.app_state = app_state

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
        "database": "connected" if app_state.ingestion_service else "not_initialized",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Football Intelligence API",
        "version": "0.1.0",
        "docs": "/docs",
    }
