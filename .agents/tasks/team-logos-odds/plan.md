# Team Logos + İddaa Oranları Implementation Plan

**Status:** Planning
**Date:** 2026-10-10

## 1. CURRENT ARCHITECTURE ANALYSIS

### Logo Support
✅ Backend fully supports logo_url:
- `Team` entity has `logo_url` field
- `TeamInfoResponse` schema includes `logo_url`
- All providers (adapter, database, development) support `logo_url`
- API endpoints map `logo_url` correctly

### Odds Support
⚠️ Odds architecture exists but NOT integrated with real provider:
- `odds_service.py` exists with full value calculation logic
- Prediction schemas support `real_odds`, `bookmaker_odds`
- API has `has_bookmaker_odds` flag (always False currently)
- No real odds provider integration exists

## 2. IMPLEMENTATION TASKS

### Phase 1: Team Logos in Match Cards

**Files to modify:**
- `frontend/src/pages/Matches.tsx` - Add logo display
- `frontend/src/pages/Upcoming.tsx` - Add logo display
- `frontend/src/pages/Completed.tsx` - Add logo display
- `frontend/src/pages/PopularLeagues.tsx` - Add logo display
- `frontend/src/pages/Dashboard.tsx` - Add logo display if applicable
- `frontend/src/pages/Matches.css` - Add logo styles

**Implementation:**
```tsx
// Current structure
<div className="team team--home">
  <span className="team-name">{match.homeTeam.name}</span>
</div>

// New structure with logo
<div className="team team--home">
  {match.homeTeam.logoUrl ? (
    <img 
      src={match.homeTeam.logoUrl} 
      alt={match.homeTeam.name}
      className="team-logo"
      onError={(e) => e.currentTarget.style.display = 'none'}
    />
  ) : (
    <div className="team-logo-placeholder">
      {match.homeTeam.code || match.homeTeam.name.substring(0, 3)}
    </div>
  )}
  <span className="team-name">{match.homeTeam.name}</span>
</div>
```

**CSS additions:**
```css
.team-logo {
  width: 32px;
  height: 32px;
  object-fit: contain;
  border-radius: 4px;
}

.team-logo-placeholder {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #0ea5e9;
}
```

### Phase 2: İddaa Oranları Analysis

**Current situation:**
- No real odds API integration
- No İddaa API credentials
- No odds provider configured
- Backend supports odds but doesn't fetch them

**Options for odds integration:**

#### Option A: User provides İddaa API access
- Requires: API key, endpoint, documentation
- Implementation: Create odds provider similar to FotMob/Ryzellx
- Timeline: 1-2 days after credentials received
- Risk: API may have rate limits or restrictions

#### Option B: User provides odds manually
- Create admin interface to input odds per match
- Store odds in database with timestamp
- Display in match cards
- Timeline: 1 day
- Risk: Manual maintenance burden

#### Option C: Mock odds display (NOT ACCEPTABLE)
- Violates PROJECT_SPEC Rule #10: "Never invent statistics, probabilities, odds"
- Violates AGENTS.md Rule #10: "Never invent... odds"
- **DO NOT IMPLEMENT THIS**

#### Option D: Show only fair odds from model
- Display model's fair odds (already calculated)
- Label clearly as "Model Fair Odds" not "İddaa Odds"
- Add note: "Real İddaa odds pending integration"
- Timeline: 2 hours
- Risk: None, fully compliant

**Recommended approach:** Option D immediately, then Option A or B when user provides access.

### Phase 3: Market Display Format

**Match card odds section structure:**
```tsx
<div className="match-card__odds">
  <div className="odds-section">
    <div className="odds-header">Tahmin Oranları</div>
    <div className="odds-grid">
      <div className="odds-item">
        <span className="odds-label">Ev Sahibi</span>
        <span className="odds-value">{homeWinOdds}</span>
      </div>
      <div className="odds-item">
        <span className="odds-label">Beraberlik</span>
        <span className="odds-value">{drawOdds}</span>
      </div>
      <div className="odds-item">
        <span className="odds-label">Deplasman</span>
        <span className="odds-value">{awayWinOdds}</span>
      </div>
    </div>
  </div>
  
  {/* Additional markets if available */}
  <div className="odds-section">
    <div className="odds-header">Diğer Marketler</div>
    <div className="odds-grid">
      <div className="odds-item">
        <span className="odds-label">Alt 2.5</span>
        <span className="odds-value">{under25Odds || '—'}</span>
      </div>
      <div className="odds-item">
        <span className="odds-label">Üst 2.5</span>
        <span className="odds-value">{over25Odds || '—'}</span>
      </div>
      <div className="odds-item">
        <span className="odds-label">KG Var</span>
        <span className="odds-value">{bttsYesOdds || '—'}</span>
      </div>
    </div>
  </div>
</div>
```

## 3. DATA FLOW

### Current prediction endpoint response:
```json
{
  "match_id": "...",
  "market_analysis": [
    {
      "market_type": "match_result",
      "outcomes": [
        {
          "label": "Home",
          "model_probability": 0.45,
          "fair_odds": 2.22,
          "real_odds": null,
          "implied_probability": null
        }
      ],
      "has_bookmaker_odds": false
    }
  ]
}
```

### What we can show NOW:
- Fair odds from model (always available)
- Model probabilities
- Clear label: "Model Fair Odds" or "Tahmin Oranları"

### What requires real integration:
- Real İddaa odds
- Bookmaker comparison
- Value indicators
- Odds movement

## 4. IMPLEMENTATION SEQUENCE

### Step 1: Logos (2 hours)
1. Read current match card implementations
2. Add logo rendering with fallback
3. Update CSS for logo display
4. Test with current data (FotMob/Ryzellx already provide logos)
5. Verify build

### Step 2: Fair Odds Display (2 hours)
1. Add odds section to match cards
2. Fetch prediction data for matches
3. Display fair odds from model
4. Label clearly as model odds, not İddaa
5. Add "Real odds integration pending" note
6. Verify build

### Step 3: User Decision Point
**ASK USER:**
- Do you have İddaa API access? (credentials, endpoints, docs)
- Should we create manual odds entry interface?
- Should we proceed with fair odds only for now?

### Step 4: Real Odds Integration (conditional on Step 3)
- Only implement after user provides access method
- Never fabricate odds
- Always mark unavailable odds with "—" or clear label

## 5. VERIFICATION CHECKLIST

- [ ] Logos display correctly for teams that have them
- [ ] Fallback placeholder shows for teams without logos
- [ ] Logo error handling (broken URLs)
- [ ] Logos maintain aspect ratio
- [ ] Logos are same size across all cards
- [ ] Fair odds display correctly
- [ ] Fair odds are clearly labeled (not confused with real İddaa)
- [ ] Missing odds show "—" not fake values
- [ ] No fabricated odds anywhere
- [ ] All match card pages updated consistently
- [ ] Responsive design maintained
- [ ] Build succeeds
- [ ] No TypeScript errors

## 6. COMPLIANCE NOTES

**Must comply with:**
- PROJECT_SPEC Rule #10: Never invent statistics, odds
- PROJECT_SPEC Rule #11: Numerical prediction engines are source of truth
- PROJECT_SPEC Rule #14: Missing info must be explicitly unavailable
- AGENTS.md Rule #10: Never invent odds
- AGENTS.md Rule #13: AI Analyst must never modify supplied numerical values

**Safe to implement:**
✅ Team logos (data exists, no fabrication)
✅ Fair odds from model (calculated, labeled correctly)
✅ "—" for unavailable data
✅ Clear labels distinguishing model vs real odds

**NOT safe to implement:**
❌ Fake İddaa odds
❌ Random odds values
❌ Odds from external scraping without permission
❌ Odds with unclear source

## 7. NEXT STEPS

1. **Implement logos immediately** (backend ready, just frontend update)
2. **Implement fair odds display** (model already calculates, just show them)
3. **Report current status to user**
4. **Ask user for İddaa integration method**
5. **Wait for user decision** before real odds integration

---

**Ready to start:** Logo implementation
**Blocked on:** Real İddaa odds (need user input)
**Compliance:** Full
