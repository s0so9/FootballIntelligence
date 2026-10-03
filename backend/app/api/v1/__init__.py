"""API version 1 module."""

from fastapi import APIRouter

from app.api.v1.endpoints import matches

# Create API v1 router
api_router = APIRouter(prefix="/api/v1")

# Include endpoint routers
api_router.include_router(matches.router)

__all__ = ["api_router"]
