#!/usr/bin/env python3
"""Check for LIVE matches in database."""

from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///football_intelligence.db')

with engine.connect() as conn:
    # Check for LIVE matches in database
    result = conn.execute(text("SELECT COUNT(*) FROM matches WHERE status = 'LIVE'"))
    live_count = result.first()[0]
    print(f"Database LIVE matches: {live_count}")
    
    if live_count > 0:
        result = conn.execute(text("""
            SELECT id, scheduled_at, home_team_id, away_team_id 
            FROM matches 
            WHERE status = 'LIVE' 
            LIMIT 5
        """))
        print("Sample LIVE matches:")
        for row in result:
            print(f"  {row[0][:8]}: {row[1]}")
    else:
        print("No LIVE matches in database - external provider being called")