#!/usr/bin/env python3
"""Check FotMob matches team IDs."""

from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///football_intelligence.db')

with engine.connect() as conn:
    # Check fotmob matches
    print("FotMob matches team ID status:")
    print("-" * 80)
    
    result = conn.execute(text("""
        SELECT id, home_team_id, away_team_id, provider_source_id, provider_id
        FROM matches 
        WHERE id LIKE 'fotmob_%' 
          AND status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
        LIMIT 5
    """))
    
    for row in result:
        match_id, home_id, away_id, source, provider_id = row
        print(f"Match: {match_id}")
        print(f"  home_team_id: {home_id if home_id else '<NULL>'}")
        print(f"  away_team_id: {away_id if away_id else '<NULL>'}")
        print(f"  provider: {source}:{provider_id}")
        print()
    
    # Count fotmob matches with/without team IDs
    result = conn.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN home_team_id IS NULL THEN 1 ELSE 0 END) as null_home,
            SUM(CASE WHEN away_team_id IS NULL THEN 1 ELSE 0 END) as null_away
        FROM matches 
        WHERE id LIKE 'fotmob_%'
          AND status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
    """))
    
    row = result.first()
    print("-" * 80)
    print(f"Total FotMob future SCHEDULED matches: {row[0]}")
    print(f"Matches with NULL home_team_id: {row[1]}")
    print(f"Matches with NULL away_team_id: {row[2]}")
    
    # Check non-fotmob matches (UUID-based)
    print()
    print("=" * 80)
    print("UUID-based matches team ID status:")
    print("-" * 80)
    
    result = conn.execute(text("""
        SELECT id, home_team_id, away_team_id, provider_source_id, provider_id
        FROM matches 
        WHERE id NOT LIKE 'fotmob_%'
          AND status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
        LIMIT 5
    """))
    
    for row in result:
        match_id, home_id, away_id, source, provider_id = row
        print(f"Match: {match_id[:16]}...")
        print(f"  home_team_id: {home_id[:16] if home_id else '<NULL>'}...")
        print(f"  away_team_id: {away_id[:16] if away_id else '<NULL>'}...")
        print(f"  provider: {source}:{provider_id}")
        print()
    
    result = conn.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN home_team_id IS NULL THEN 1 ELSE 0 END) as null_home,
            SUM(CASE WHEN away_team_id IS NULL THEN 1 ELSE 0 END) as null_away
        FROM matches 
        WHERE id NOT LIKE 'fotmob_%'
          AND status = 'SCHEDULED' 
          AND scheduled_at > datetime('now')
    """))
    
    row = result.first()
    print("-" * 80)
    print(f"Total UUID-based future SCHEDULED matches: {row[0]}")
    print(f"Matches with NULL home_team_id: {row[1]}")
    print(f"Matches with NULL away_team_id: {row[2]}")
