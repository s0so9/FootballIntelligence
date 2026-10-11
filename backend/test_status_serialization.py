#!/usr/bin/env python3
"""Test script for match status serialization issue."""

import sys
sys.path.insert(0, '.')

from app.providers.adapter import ProviderManagerAdapter
from app.core.config import get_settings
import asyncio
import json

async def test():
    settings = get_settings()
    adapter = ProviderManagerAdapter(settings)
    
    matches = await adapter.get_matches_async(status='scheduled')
    print(f'Provider returned {len(matches)} matches')
    
    if matches:
        match = matches[0]
        print(f'First match status: {match.status} (type: {type(match.status)})')
        print(f'First match status.value: {match.status.value}')
        
        # Test serialization
        from app.api.v1.schemas import MatchResponse
        from app.domain.entities import Team as DomainTeam
        
        home_team = DomainTeam(
            id=match.home_team_id,
            name='Test Home',
            short_name='THM',
            code='THM',
            logo_url=None
        )
        
        away_team = DomainTeam(
            id=match.away_team_id,
            name='Test Away',
            short_name='TAW',
            code='TAW',
            logo_url=None
        )
        
        try:
            response = MatchResponse(
                id=match.id,
                competition_id=match.competition_id,
                competition_name='Test League',
                season_id=match.season_id,
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                venue_id=match.venue_id,
                home_team={
                    'id': home_team.id, 
                    'name': home_team.name, 
                    'short_name': home_team.short_name, 
                    'code': home_team.code, 
                    'logo_url': home_team.logo_url
                },
                away_team={
                    'id': away_team.id, 
                    'name': away_team.name, 
                    'short_name': away_team.short_name, 
                    'code': away_team.code, 
                    'logo_url': away_team.logo_url
                },
                scheduled_at=match.scheduled_at,
                status=match.status,
                home_score=match.home_score,
                away_score=match.away_score,
                home_score_ht=match.home_score_ht,
                away_score_ht=match.away_score_ht,
                home_statistics=None,
                away_statistics=None,
                home_statistics_ht=None,
                away_statistics_ht=None,
                minute=match.minute,
                added_time=match.added_time,
                outcome=match.outcome,
                round=match.round,
                created_at=match.created_at,
                updated_at=match.updated_at,
                provider_fetched_at=match.provider_fetched_at,
            )
            print('Schema creation SUCCESS')
            
            # Test JSON serialization
            json_str = response.model_dump_json()
            print('JSON serialization SUCCESS')
            
            parsed = json.loads(json_str)
            print(f'Status in JSON: {parsed["status"]}')
            
        except Exception as e:
            print(f'Schema/Serialization ERROR: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())