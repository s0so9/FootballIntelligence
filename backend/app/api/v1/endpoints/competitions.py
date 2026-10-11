"""Competition endpoints for API v1.

This module implements competition-related REST API endpoints.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_data_provider
from app.api.v1.schemas import (
    CompetitionListResponse,
    CompetitionResponse,
)
from app.providers import FootballDataProvider


router = APIRouter(prefix="/competitions", tags=["competitions"])

# Popular competition name keywords used to filter the DB competition list.
# Matched case-insensitively against competition.name.
_POPULAR_KEYWORDS = [
    "premier league",
    "bundesliga",
    "laliga",
    "la liga",
    "serie a",
    "ligue 1",
    "champions league",
    "europa league",
    "super lig",
    "eredivisie",
    "primeira liga",
    "scottish premiership",
]


def _is_popular(name: str) -> bool:
    """Return True if the competition name matches a popular league keyword."""
    name_lower = name.lower().strip()
    return any(kw in name_lower for kw in _POPULAR_KEYWORDS)


@router.get(
    "",
    response_model=CompetitionListResponse,
    summary="List competitions",
    description="Get a list of available competitions/leagues.",
)
async def list_competitions(
    provider: FootballDataProvider = Depends(get_data_provider),
) -> CompetitionListResponse:
    """
    List available competitions.

    Returns a curated list of major competitions available from the data provider.
    Competitions are filtered to popular major leagues by name keyword matching.

    Returns:
        CompetitionListResponse containing list of competitions
    """
    if provider.is_development_data():
        # Development data: match DevelopmentProvider competition IDs
        major_competitions = [
            CompetitionResponse(
                id="dev_comp_league_a",
                name="[DEV] League A",
                country="DEV",
            ),
            CompetitionResponse(
                id="dev_comp_league_b",
                name="[DEV] League B",
                country="DEV",
            ),
        ]
    else:
        # Real data: query provider (HybridProvider -> DB fallback) and filter by
        # popular league name keywords.  Never use hardcoded competition UUIDs
        # because those IDs are provider/DB-specific and change between datasets.
        major_competitions = []

        try:
            all_competitions = provider.get_competitions()

            # Deduplicate by name: keep first occurrence of each canonical name.
            # The provider returns competitions in DB insertion order; for names
            # that appear multiple times (e.g. "Premier League" for different
            # countries) the first entry is kept.
            seen_names: set = set()
            for comp in all_competitions:
                if not comp.name:
                    continue
                if not _is_popular(comp.name):
                    continue
                canonical = comp.name.strip()
                if canonical in seen_names:
                    continue
                seen_names.add(canonical)
                major_competitions.append(
                    CompetitionResponse(
                        id=comp.id,
                        name=comp.name,
                        country=comp.country,
                    )
                )
        except Exception:
            # If provider fails entirely, return an empty list rather than
            # returning wrong hardcoded UUIDs that produce empty match results.
            major_competitions = []

    return CompetitionListResponse(
        competitions=major_competitions,
        count=len(major_competitions),
        is_development_data=provider.is_development_data(),
    )
