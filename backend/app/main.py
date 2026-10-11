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
    title="TUTAR X API",
    description="TUTAR X - Maçın geleceğini veriden oku. Professional football analytics and prediction platform.",
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
    """Health check endpoint with real database connectivity verification."""
    from app.database.session import get_session_factory
    
    # Check service initialization
    service_status = "healthy" if app_state.ingestion_service else "not_initialized"
    
    # Perform actual database connectivity test
    database_status = "unknown"
    database_details = {}
    
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            # Execute a simple query to verify database connectivity
            from app.database.models import Team as TeamDB
            team_count = session.query(TeamDB).count()
            
            database_status = "connected"
            database_details = {
                "teams_count": team_count,
                "connection_verified": True
            }
            
            # Add warning for empty teams table in production
            if team_count == 0:
                database_details["warning"] = "Teams table is empty - team ID resolution will fail"
                # Log this as a warning for monitoring
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Production database teams table is empty - this will cause team ID resolution failures")
    except Exception as exc:
        database_status = "connection_failed"
        database_details = {
            "error": str(exc)[:100],  # Limit error message length for security
            "connection_verified": False
        }
    
    # Overall health determination
    overall_status = "healthy" if (service_status == "healthy" and database_status == "connected") else "degraded"
    
    return {
        "status": overall_status,
        "service": "TUTAR X API",
        "version": "0.1.0",
        "database": database_status,
        "database_details": database_details,
        "ingestion_service": service_status,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TUTAR X API",
        "version": "0.1.0",
        "docs": "/docs",
    }
