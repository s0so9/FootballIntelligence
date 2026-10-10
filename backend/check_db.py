"""Check database for historical match data."""

from app.database.session import get_db
from sqlalchemy import text

db = next(get_db())

print("="*60)
print("DATABASE CHECK")
print("="*60)

# Check matches table
result = db.execute(text('SELECT COUNT(*) FROM matches')).scalar()
print(f'\nTotal matches in DB: {result}')

if result > 0:
    # Get finished count
    finished = db.execute(text("SELECT COUNT(*) FROM matches WHERE status='FINISHED'")).scalar()
    print(f'Finished matches: {finished}')
    
    # Get date range
    dates = db.execute(text('SELECT MIN(scheduled_at), MAX(scheduled_at) FROM matches')).first()
    print(f'Date range: {dates[0]} to {dates[1]}')
    
    # Check teams 8406 and 9823
    team1 = db.execute(text("SELECT COUNT(*) FROM matches WHERE (home_team_id='8406' OR away_team_id='8406') AND status='FINISHED'")).scalar()
    team2 = db.execute(text("SELECT COUNT(*) FROM matches WHERE (home_team_id='9823' OR away_team_id='9823') AND status='FINISHED'")).scalar()
    print(f'\nTeam 8406 finished matches: {team1}')
    print(f'Team 9823 finished matches: {team2}')
    
    print("\n" + "="*60)
    print("DATABASE HAS DATA - OPTIMIZATION WILL BE ACTIVE")
    print("="*60)
else:
    print("\n" + "="*60)
    print("DATABASE IS EMPTY - WILL FALLBACK TO PROVIDER")
    print("="*60)

db.close()
