"""API version 1 module."""

from fastapi import APIRouter

from app.api.v1.endpoints import matches, live_matches, competitions

# Create API v1 router
api_router = APIRouter(prefix="/api/v1")

# Include endpoint routers
# IMPORTANT: live_matches must be registered BEFORE matches to prevent
# /{match_id} from capturing /live as a match_id parameter
api_router.include_router(competitions.router)
api_router.include_router(live_matches.router)
api_router.include_router(matches.router)

__all__ = ["api_router"]
