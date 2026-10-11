#!/usr/bin/env python3
"""Check provider mapping in database."""

from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///football_intelligence.db')

with engine.connect() as conn:
    # Check provider_source_id and provider_id mapping
    print("Database matches provider mapping:")
    print("-" * 80)
    
    result = conn.execute(text("""
        SELECT 
            id, 
            provider_source_id, 
            provider_id,
            home_team_id,
            away_team_id
        FROM matches 
        WHERE status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
        ORDER BY scheduled_at
        LIMIT 5
    """))
    
    for row in result:
        match_id, source_id, provider_id, home_id, away_id = row
        print(f"Match UUID: {match_id[:16]}...")
        print(f"  provider_source_id: {source_id}")
        print(f"  provider_id: {provider_id}")
        print(f"  home_team_id: {home_id[:16] if home_id else 'NULL'}...")
        print(f"  away_team_id: {away_id[:16] if away_id else 'NULL'}...")
        print()
    
    # Check if provider_id format matches FotMob external format
    result = conn.execute(text("""
        SELECT COUNT(*) as total
        FROM matches 
        WHERE status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
          AND provider_id IS NOT NULL
          AND provider_id != ''
    """))
    
    row = result.first()
    print("-" * 80)
    print(f"Future SCHEDULED matches with provider_id: {row[0]}")
    
    # Check provider_source_id patterns
    result = conn.execute(text("""
        SELECT DISTINCT provider_source_id, COUNT(*) as cnt
        FROM matches 
        WHERE status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
        GROUP BY provider_source_id
        ORDER BY cnt DESC
    """))
    
    print("\nProvider source distribution:")
    for row in result:
        print(f"  {row[0]}: {row[1]} matches")
