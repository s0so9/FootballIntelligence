#!/usr/bin/env python3
"""Check if matches have corresponding team records."""

from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///football_intelligence.db')

with engine.connect() as conn:
    # Check future SCHEDULED matches with team names
    result = conn.execute(text("""
        SELECT 
            m.id, 
            m.home_team_id, 
            m.away_team_id, 
            ht.name as home_name, 
            at.name as away_name,
            m.provider_source_id,
            m.provider_id
        FROM matches m 
        LEFT JOIN teams ht ON m.home_team_id = ht.id 
        LEFT JOIN teams at ON m.away_team_id = at.id 
        WHERE m.status = 'SCHEDULED' AND m.scheduled_at > datetime('now')
        LIMIT 10
    """))
    
    print("Sample future SCHEDULED matches with team info:")
    print("-" * 80)
    missing_count = 0
    for row in result:
        match_id, home_id, away_id, home_name, away_name, source, provider_id = row
        home_display = f"{home_name}" if home_name else f"<MISSING: {home_id[:8] if home_id else 'NULL'}>"
        away_display = f"{away_name}" if away_name else f"<MISSING: {away_id[:8] if away_id else 'NULL'}>"
        
        if not home_name or not away_name:
            missing_count += 1
            
        print(f"{match_id[:8]}: {home_display} vs {away_display}")
        print(f"  Provider: {source}:{provider_id}")
        print()
    
    # Count matches with missing teams
    result = conn.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ht.id IS NULL THEN 1 ELSE 0 END) as missing_home,
            SUM(CASE WHEN at.id IS NULL THEN 1 ELSE 0 END) as missing_away
        FROM matches m 
        LEFT JOIN teams ht ON m.home_team_id = ht.id 
        LEFT JOIN teams at ON m.away_team_id = at.id 
        WHERE m.status = 'SCHEDULED' AND m.scheduled_at > datetime('now')
    """))
    
    row = result.first()
    print("-" * 80)
    print(f"Total future SCHEDULED matches: {row[0]}")
    print(f"Matches with missing home team: {row[1]}")
    print(f"Matches with missing away team: {row[2]}")
    print(f"Matches with at least one missing team: {row[1] + row[2] if row[1] and row[2] else 'N/A'}")
