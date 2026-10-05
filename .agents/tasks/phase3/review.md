# Backend Match Intelligence with First-Half Statistics and Team Logos

Phase 3 adds match statistics, first-half data, and team logos to the match endpoints. The implementation preserves existing prediction logic, maintains backward compatibility, and enforces the no-fabrication rule — first-half statistics are distinct values, not computed from full-match data.

**Watch for:** Silent NotImplementedError handling **(likely)** — the try/except around first-half statistics catches NotImplementedError but never logs when a provider doesn't support the feature, which could mask integration issues when real providers are added.

**Verdict**: APPROVED

## High-level view

Team logos flow through the existing Team domain model (logo_url added to mock data) and surface via TeamInfoResponse in both list and detail endpoints. Missing logos return null, not placeholders.

Match statistics populate only for finished matches through the existing get_team_match_statistics interface. Scheduled matches return null for all statistics fields. The endpoint queries statistics once per match, loops over results by team_id, and maps to response schemas.

First-half statistics use a new provider method (get_team_match_statistics_firsthalf) wrapped in try/except. When the provider raises NotImplementedError, the endpoint silently leaves home_statistics_ht and away_statistics_ht as None. The DevelopmentProvider implements this method with distinct mock values that are internally consistent but deliberately not derived from full-match totals.

Backward compatibility preserved: new fields (home_statistics_ht, away_statistics_ht, home_team, away_team) default to None, existing tests pass, and the prediction endpoint remains untouched.

<details>
<summary>Issues (1)</summary>

1. **Silent first-half provider failure** — When a provider doesn't implement get_team_match_statistics_firsthalf, the try/except block catches NotImplementedError and continues silently. Consider logging at debug level when this occurs so integration with real providers can be verified without inspecting API responses. Not blocking because the current DevelopmentProvider implements the method and the fallback behavior (None) is correct.

</details>

<details>
<summary>Details</summary>

## Team identity enrichment in match endpoints

Both GET /matches and GET /matches/{match_id} now call provider.get_team(team_id) for home and away teams, mapping the Team domain model to TeamInfoResponse. The Team.logo_url field flows through unchanged — null when unavailable, URL string otherwise. The DevelopmentProvider sets logo_url for three of four mock teams (alpha, beta, delta have URLs; gamma has None).

The enrichment happens after retrieving match data but before building the response schema. For the list endpoint, this adds 2 provider calls per match (home_team_id, away_team_id). For a typical list of 10 matches, that's 20 additional queries. The DevelopmentProvider holds teams in memory so this is fast, but when a real provider with network I/O is added, consider whether batch-fetching teams or caching team metadata would be appropriate.

TeamInfoResponse includes id, name, short_name, code, and logo_url. The logo_url is typed Optional[str] and set directly from Team.logo_url. No fallback, no placeholder generation.

## Match statistics gating by status

Statistics population is gated on `match.status == MatchStatus.FINISHED`. If the match is scheduled, live, postponed, or any status other than finished, home_statistics and away_statistics remain None.

After the status check passes, the endpoint calls provider.get_team_match_statistics(match_id) once. This returns a list of TeamMatchStatistic domain models (one per team). The endpoint loops over the list, checking stat.team_id against match.home_team_id and match.away_team_id to assign home_statistics and away_statistics.

The mapping helper _map_statistic_to_response translates the domain model to MatchStatisticsResponse, copying all 22 fields. If a field is absent in the domain model (unlikely given TeamMatchStatistic's structure), the response field would be None.

The DevelopmentProvider supplies statistics for three finished matches: dev_match_001 (alpha vs beta, 2-1), dev_match_003 (beta vs gamma, 1-1), dev_match_004 (delta vs alpha, 0-3). Scheduled match dev_match_002 has no statistics, and the endpoint correctly returns None for both teams.

## First-half statistics with provider abstraction

First-half statistics follow the same pattern as full-match statistics but use a new provider method: get_team_match_statistics_firsthalf. The base provider interface defines this method with a NotImplementedError default, marking it optional.

In matches.py, after populating full-match statistics, the endpoint attempts to fetch first-half data:

```python
try:
    ht_stats = provider.get_team_match_statistics_firsthalf(match.id)
    for stat in ht_stats:
        if stat.team_id == match.home_team_id:
            home_statistics_ht = _map_statistic_to_response(stat)
        elif stat.team_id == match.away_team_id:
            away_statistics_ht = _map_statistic_to_response(stat)
except NotImplementedError:
    pass
```

When the provider doesn't implement first-half statistics, the exception is caught and the endpoint continues. home_statistics_ht and away_statistics_ht remain None (their initialized value). This is correct behavior, but the silent catch means there's no log entry when a provider doesn't support the feature. During integration with a real provider, you won't know whether first-half stats are unsupported or whether the provider implementation has a bug unless you inspect API responses or add debug logging.

The DevelopmentProvider implements get_team_match_statistics_firsthalf with distinct mock data. For dev_match_001, the full-match home shots_total is 15; the first-half home shots_total is 8. These are not related by division — the test `test_firsthalf_not_computed_from_fullmatch` confirms 8 != 15/2.

First-half goals_scored align with home_score_ht and away_score_ht from the Match model. For dev_match_001: home_score_ht=1, home_statistics_ht.goals_scored=1. For dev_match_004: home_score_ht=0, away_score_ht=2, matching the respective goals_scored in first-half stats.

All first-half values are plausible subsets of full-match totals: HT shots <= full shots, HT corners <= full corners, HT cards <= full cards. The test suite verifies this across all three finished matches.

## Schema and type additions

MatchResponse gained two fields:
- home_statistics_ht: Optional[MatchStatisticsResponse]
- away_statistics_ht: Optional[MatchStatisticsResponse]

Both default to None. The schema uses the existing MatchStatisticsResponse structure (22 fields covering goals, xG, shots, possession, passing, set pieces, discipline, and defensive stats). No new statistic types were added; first-half data reuses the full-match schema.

The frontend type definition (types.ts) mirrors this: home_statistics_ht and away_statistics_ht are typed `MatchStatisticsResponse | null`, matching the backend contract.

TeamInfoResponse already existed; no changes were needed. The logo_url field was already defined as `string | null` in both backend schema and frontend type.

## Test coverage

test_match_intelligence.py adds 25 tests covering:
- Team info presence and structure in match list (4 tests)
- Statistics presence/absence based on match status (5 tests)
- First-half statistics existence and validation (6 tests)
- Backward compatibility (4 tests)
- Internal consistency of statistics (4 tests)
- Team identity stability across endpoints (2 tests)

Critical test: `test_firsthalf_not_computed_from_fullmatch` reads dev_match_001, extracts home_statistics.shots_total (15) and home_statistics_ht.shots_total (8), and asserts `8 != 15/2`. The assertion message explicitly flags if first-half appears to be computed from full-match. This test would catch accidental fabrication.

Another key test: `test_firsthalf_goals_match_halftime_score` verifies goals_scored in first-half statistics equals home_score_ht and away_score_ht from the Match model. This ensures first-half stats are consistent with the existing half-time score data.

`test_team_logo_can_be_null` finds dev_team_gamma (which has logo_url=None in the provider) and confirms the API returns null, not a placeholder or empty string.

All 25 tests pass. The spot-check I ran confirmed this (25 passed, 44 warnings related to Pydantic deprecations and datetime.utcnow, none blocking).

</details>

<details>
<summary>File map</summary>

### Modified files

- **backend/app/api/v1/schemas.py** — Added home_statistics_ht and away_statistics_ht fields to MatchResponse
- **backend/app/api/v1/endpoints/matches.py** — Enriched list_matches and get_match to populate team info, statistics, and first-half statistics
- **backend/app/providers/base.py** — Added get_team_match_statistics_firsthalf method to FootballDataProvider interface
- **backend/app/providers/development.py** — Added logo_url to teams, comprehensive statistics for all finished matches, and distinct first-half statistics
- **backend/tests/test_match_intelligence.py** — New test file with 25 tests covering team logos, statistics, first-half data, and backward compatibility
- **frontend/src/api/types.ts** — Added home_statistics_ht and away_statistics_ht to MatchResponse interface

</details>
