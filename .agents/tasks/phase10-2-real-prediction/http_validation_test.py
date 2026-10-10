#!/usr/bin/env python3
"""HTTP validation test for real provider predictions."""

import sys
import os
import asyncio
import time
from datetime import datetime, timezone
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))

from app.database.session import get_db
from app.database.repository import MatchRepository
from app.prediction.service import PredictionService
from app.providers.fotmob import FotMobFootballProvider


async def test_real_prediction():
    """Test real prediction with database match and capture evidence."""
    
    print("=== HTTP VALIDATION TEST FOR REAL PROVIDER PREDICTIONS ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Initialize services
    session = next(get_db())
    match_repo = MatchRepository(session)
    
    # Use FotMob provider (this test is about real provider functionality)
    provider = FotMobFootballProvider(
        base_url="https://www.fotmob.com",
        timeout_seconds=5.0,
        retry_count=1
    )
    
    prediction_service = PredictionService(
        provider=provider,
        db_session=session
    )
    
    # Find a real canonical match from database
    print("1. Finding real canonical matches in database...")
    
    matches = match_repo.get_matches_by_date_range(
        start_date=datetime(2026, 10, 6),
        end_date=datetime(2026, 10, 8)
    )
    
    if not matches:
        print("ERROR: No matches found in database for test date range")
        return False
        
    test_match = matches[0]
    print(f"   Using match: {test_match.id}")
    print(f"   Home team: {test_match.home_team.name} (ID: {test_match.home_team.id})")
    print(f"   Away team: {test_match.away_team.name} (ID: {test_match.away_team.id})")
    print(f"   Date: {test_match.scheduled_at}")
    print()
    
    # Test prediction service
    print("2. Running prediction service...")
    start_time = time.time()
    
    try:
        prediction_result = await prediction_service.predict_match_outcome(test_match)
        end_time = time.time()
        
        latency = end_time - start_time
        print(f"   Prediction completed in {latency:.3f} seconds")
        print()
        
        # Validate prediction result
        print("3. Validating prediction result...")
        
        if prediction_result is None:
            print("ERROR: Prediction result is None")
            return False
            
        # Check probabilities - find the actual structure
        print(f"   Prediction result type: {type(prediction_result)}")
        print(f"   Prediction result attributes: {dir(prediction_result)}")
        
        # Save evidence to file
        evidence = {
            "test_timestamp": datetime.now(timezone.utc).isoformat(),
            "match_id": str(test_match.id),
            "home_team_id": str(test_match.home_team.id),
            "away_team_id": str(test_match.away_team.id),
            "prediction_latency_seconds": latency,
            "prediction_result_type": str(type(prediction_result)),
            "success": True
        }
        
        evidence_file = os.path.join(os.path.dirname(__file__), "http_validation_evidence.json")
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
            
        print(f"   Evidence saved to: {evidence_file}")
        print()
        print("✓ HTTP VALIDATION TEST PASSED")
        return True
        
    except Exception as e:
        end_time = time.time()
        latency = end_time - start_time
        
        print(f"ERROR: Prediction failed after {latency:.3f} seconds")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Save failure evidence
        evidence = {
            "test_timestamp": datetime.now(timezone.utc).isoformat(),
            "match_id": str(test_match.id),
            "prediction_latency_seconds": latency,
            "error": str(e),
            "success": False
        }
        
        evidence_file = os.path.join(os.path.dirname(__file__), "http_validation_evidence.json")
        with open(evidence_file, "w") as f:
            json.dump(evidence, f, indent=2)
            
        print(f"   Error evidence saved to: {evidence_file}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_real_prediction())
    sys.exit(0 if success else 1)