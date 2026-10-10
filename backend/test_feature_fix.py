"""Test feature name fix for PoissonModel."""
import sys
from app.database import get_session_factory
from app.database.models import Match as DBMatch
from app.domain.match import Match
from app.features.match_features import MatchFeatureExtractor
from app.providers import ProviderManager

# Get test match from DB
session = get_session_factory()()
db_match = session.query(DBMatch).filter(DBMatch.id == '47cea9fe-85e0-4c71-9614-ab18f60ce356').first()

if not db_match:
    print("[ERROR] Match not found in database")
    sys.exit(1)

print(f"[OK] Match found: {db_match.id}")
print(f"   Home: {db_match.home_team_id}")
print(f"   Away: {db_match.away_team_id}")
print(f"   Date: {db_match.scheduled_at}")

# Convert to domain match
match = Match(
    id=db_match.id,
    home_team_id=db_match.home_team_id,
    away_team_id=db_match.away_team_id,
    competition_id=db_match.competition_id,
    season_id=db_match.season,
    scheduled_at=db_match.scheduled_at,
    status=db_match.status,
    home_score=db_match.home_score,
    away_score=db_match.away_score,
)

# Extract features
provider = ProviderManager()
extractor = MatchFeatureExtractor(provider=provider, db_session=session)

print("\n[INFO] Extracting features...")
features = extractor.extract_features(match)

# Check required features
required = ["home_goals_scored_avg", "away_goals_scored_avg"]
print("\n[CHECK] Required features for PoissonModel:")
for feat in required:
    value = features.get(feat)
    status = "[OK]" if value is not None else "[FAIL]"
    print(f"   {status} {feat}: {value}")

# Check alternative features
alternatives = ["home_attack_strength", "away_attack_strength"]
print("\n[CHECK] Alternative feature names:")
for feat in alternatives:
    value = features.get(feat)
    status = "[OK]" if value is not None else "[FAIL]"
    print(f"   {status} {feat}: {value}")

session.close()

if features.get("home_goals_scored_avg") and features.get("away_goals_scored_avg"):
    print("\n[SUCCESS] Feature fix successful!")
    sys.exit(0)
else:
    print("\n[ERROR] Feature fix failed!")
    sys.exit(1)
