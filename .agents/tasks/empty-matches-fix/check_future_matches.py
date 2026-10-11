#!/usr/bin/env python3
"""Check for future SCHEDULED matches in database."""

from sqlalchemy import create_engine, text
from datetime import datetime

engine = create_engine('sqlite:///football_intelligence.db')

with engine.connect() as conn:
    # Future SCHEDULED matches
    result = conn.execute(text("""
        SELECT COUNT(*) as cnt, MIN(scheduled_at) as earliest, MAX(scheduled_at) as latest 
        FROM matches 
        WHERE status = 'SCHEDULED' AND scheduled_at > datetime('now')
    """))
    row = result.first()
    print(f"Future SCHEDULED matches: {row[0]}")
    print(f"Earliest: {row[1]}")
    print(f"Latest: {row[2]}")
    print()
    
    # Past SCHEDULED matches (will be converted to FINISHED)
    result = conn.execute(text("""
        SELECT COUNT(*) as cnt, MIN(scheduled_at) as earliest, MAX(scheduled_at) as latest 
        FROM matches 
        WHERE status = 'SCHEDULED' AND scheduled_at <= datetime('now')
    """))
    row = result.first()
    print(f"Past SCHEDULED matches (will be auto-FINISHED): {row[0]}")
    print(f"Earliest: {row[1]}")
    print(f"Latest: {row[2]}")
    print()
    
    # Sample of future SCHEDULED matches
    result = conn.execute(text("""
        SELECT id, scheduled_at, provider_source_id, provider_id
        FROM matches 
        WHERE status = 'SCHEDULED' AND scheduled_at > datetime('now')
        ORDER BY scheduled_at
        LIMIT 5
    """))
    
    print("Sample future SCHEDULED matches:")
    for row in result:
        print(f"  {row[0][:8]}... {row[1]} provider: {row[2]}:{row[3]}")
