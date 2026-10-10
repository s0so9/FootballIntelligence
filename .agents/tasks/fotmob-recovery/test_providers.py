"""Test script to diagnose real provider failures."""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.providers.fotmob import FotMobFootballProvider
from app.providers.ryzellx import RyzellxFootballProvider
from app.providers.openligadb import OpenLigaDBFootballProvider


async def test_fotmob():
    """Test FotMob provider."""
    print("\n" + "="*60)
    print("TESTING FOTMOB PROVIDER")
    print("="*60)
    
    provider = FotMobFootballProvider(
        base_url="https://www.fotmob.com",
        timeout_seconds=10.0,
        retry_count=1
    )
    
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        print(f"\nFetching matches for date range: {today} to {tomorrow}")
        matches = await provider.get_matches_by_range(today, tomorrow)
        
        print(f"✓ FotMob SUCCESS: {len(matches)} matches found")
        if matches:
            print(f"\nSample match:")
            m = matches[0]
            print(f"  - ID: {m.source_id}")
            print(f"  - Competition: {m.competition_name} (ID: {m.competition_id})")
            print(f"  - Home: {m.home_team_name} (ID: {m.home_team_id})")
            print(f"  - Away: {m.away_team_name} (ID: {m.away_team_id})")
            print(f"  - Status: {m.status}")
            print(f"  - Scheduled: {m.scheduled_at}")
        
        return True, None
        
    except Exception as e:
        print(f"✗ FotMob ERROR: {type(e).__name__}")
        print(f"  Message: {str(e)[:300]}")
        import traceback
        print(f"\nFull traceback:")
        traceback.print_exc()
        return False, e
        
    finally:
        await provider.close()


async def test_ryzellx():
    """Test Ryzellx provider."""
    print("\n" + "="*60)
    print("TESTING RYZELLX PROVIDER")
    print("="*60)
    
    provider = RyzellxFootballProvider(
        base_url="http://localhost:3001",
        timeout_seconds=10.0,
        retry_count=2
    )
    
    try:
        today = date.today()
        
        print(f"\nFetching matches for date: {today}")
        matches = await provider.get_matches_by_date(today)
        
        print(f"✓ Ryzellx SUCCESS: {len(matches)} matches found")
        if matches:
            print(f"\nSample match:")
            m = matches[0]
            print(f"  - ID: {m.source_id}")
            print(f"  - Competition: {m.competition_name}")
            print(f"  - Home: {m.home_team_name} (ID: {m.home_team_id})")
            print(f"  - Away: {m.away_team_name} (ID: {m.away_team_id})")
        
        return True, None
        
    except Exception as e:
        print(f"✗ Ryzellx ERROR: {type(e).__name__}")
        print(f"  Message: {str(e)[:300]}")
        return False, e
        
    finally:
        await provider.close()


async def test_openligadb():
    """Test OpenLigaDB provider."""
    print("\n" + "="*60)
    print("TESTING OPENLIGADB PROVIDER")
    print("="*60)
    
    provider = OpenLigaDBFootballProvider(
        base_url="https://api.openligadb.de",
        timeout_seconds=10.0,
        retry_count=2
    )
    
    try:
        # OpenLigaDB doesn't support date queries, so test get_match instead
        print("\nNote: OpenLigaDB does not support date-based queries")
        print("Testing league lookup instead...")
        
        league = await provider.get_league("4432")  # Bundesliga
        
        if league:
            print(f"✓ OpenLigaDB SUCCESS: Found league '{league.name}'")
        else:
            print("✗ OpenLigaDB: No league found")
        
        return True, None
        
    except Exception as e:
        print(f"✗ OpenLigaDB ERROR: {type(e).__name__}")
        print(f"  Message: {str(e)[:300]}")
        return False, e
        
    finally:
        await provider.close()


async def main():
    """Run all provider tests."""
    print("\n" + "#"*60)
    print("# REAL PROVIDER DIAGNOSTIC TEST")
    print("#"*60)
    
    results = {}
    
    # Test FotMob
    success, error = await test_fotmob()
    results['fotmob'] = {'success': success, 'error': error}
    
    # Test Ryzellx
    success, error = await test_ryzellx()
    results['ryzellx'] = {'success': success, 'error': error}
    
    # Test OpenLigaDB
    success, error = await test_openligadb()
    results['openligadb'] = {'success': success, 'error': error}
    
    # Summary
    print("\n" + "#"*60)
    print("# SUMMARY")
    print("#"*60)
    for provider_name, result in results.items():
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"{provider_name:15s}: {status}")
        if result['error']:
            print(f"                 {type(result['error']).__name__}: {str(result['error'])[:100]}")
    
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
