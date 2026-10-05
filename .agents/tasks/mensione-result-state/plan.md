# Implementation Plan: MensionePickCard Result State Extension

## Overview

Extend the existing MensionePickCard component to display match result state (skor + durum) while preserving all current functionality. The component already exists at `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.tsx` with its CSS at `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.css`.

**Note:** The user mentioned removing "partner" props, but after inspecting the current component, no partner-related props or functionality exist. No removal work is needed.

---

## Implementation Steps

- [ ] 1. **Add result state props to MensionePickCardProps interface**
      
      Add two new optional props to the `MensionePickCardProps` interface in `MensionePickCard.tsx` (line 16):
      
      ```ts
      skor?: { ev: number; dep: number } | null
      durum?: 'won' | 'lost' | 'pending'
      ```
      
      Default behavior: when `durum` is omitted, treat as `'pending'`. When `skor` is omitted or `null`, display "vs" separator. When `skor` is present, display score box.
      
      **Files:**
      - `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.tsx`
      
      **Verify:**
      Run `npm run type-check` in `c:\FootballIntelligence\frontend` and confirm no TypeScript errors.

---

- [ ] 2. **Update collapsed-header__teams section to conditionally display score**
      
      Modify the `.collapsed-header__teams` section (currently at line ~270-274 in the TSX) to conditionally render either:
      
      - When `skor` is `null` or `undefined`: keep existing display
        ```tsx
        <span className="team-name">{homeTeam}</span>
        <span className="vs-separator">vs</span>
        <span className="team-name">{awayTeam}</span>
        ```
      
      - When `skor` is present: display score box
        ```tsx
        <span className="team-name">{homeTeam}</span>
        <div className="score-box">
          <span className="score-home">{skor.ev}</span>
          <span className="score-separator">—</span>
          <span className="score-away">{skor.dep}</span>
        </div>
        <span className="team-name">{awayTeam}</span>
        ```
      
      **Files:**
      - `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.tsx`
      
      **Verify:**
      Run `npm run type-check` in `c:\FootballIntelligence\frontend` and confirm no TypeScript errors. Visual verification will happen after CSS is added.

---

- [ ] 3. **Update collapsed-header__intelligence section to conditionally display result badge**
      
      Modify the `.collapsed-header__intelligence` section (currently at line ~287-310 in the TSX). The current code always renders the `.intelligence-compact` block with "AI GÜVENİ" label.
      
      Replace the existing intelligence-compact block with conditional rendering based on `durum`:
      
      **When `durum === 'pending'` or `durum` is undefined:**
      ```tsx
      <div className="intelligence-compact">
        <div className="intelligence-compact__label">AI GÜVENİ</div>
        <AIConfidence 
          confidence={confidence} 
          size="sm"
          showPercentage={false}
          showLevel={false}
          showLabel={false}
        />
      </div>
      ```
      
      **When `durum === 'won'`:**
      ```tsx
      <div className="result-badge result-badge--won" aria-label="Sonuç: Kazandı">
        <span className="result-badge__icon">✓</span>
        <span className="result-badge__text">WON</span>
      </div>
      ```
      
      **When `durum === 'lost'`:**
      ```tsx
      <div className="result-badge result-badge--lost" aria-label="Sonuç: Kaybetti">
        <span className="result-badge__icon">✕</span>
        <span className="result-badge__text">LOST</span>
      </div>
      ```
      
      Implementation approach: Use a ternary or if/else to render the appropriate block based on `durum ?? 'pending'`.
      
      **Files:**
      - `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.tsx`
      
      **Verify:**
      Run `npm run type-check` in `c:\FootballIntelligence\frontend` and confirm no TypeScript errors.

---

- [ ] 4. **Add CSS styles for score-box and result-badge**
      
      Add the following CSS rules to `MensionePickCard.css` after the existing `.intelligence-compact__value--gold` rule (around line 183):
      
      **Score Box Styles:**
      ```css
      /* Score Box - Match Result Display */
      .score-box {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: #0a0f0c;
        border: 1px solid #2a2f2c;
        border-radius: 12px;
        font-variant-numeric: tabular-nums;
      }
      
      .score-home,
      .score-away {
        font-size: 28px;
        font-weight: 700;
        color: var(--color-text-primary);
        line-height: 1;
        font-family: monospace;
      }
      
      .score-separator {
        font-size: 20px;
        font-weight: 400;
        color: #9aa39e;
        line-height: 1;
      }
      ```
      
      **Result Badge Styles:**
      ```css
      /* Result Badge - Won/Lost Indicator */
      .result-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      
      .result-badge--won {
        background: rgba(46, 226, 123, 0.12);
        border: 1px solid rgba(46, 226, 123, 0.3);
        color: #2ee27b;
      }
      
      .result-badge--lost {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #ef4444;
      }
      
      .result-badge__icon {
        font-size: 14px;
        line-height: 1;
      }
      
      .result-badge__text {
        line-height: 1;
      }
      ```
      
      **Files:**
      - `c:\FootballIntelligence\frontend\src\components\predictions\MensionePickCard.css`
      
      **Verify:**
      Run `npm run build` in `c:\FootballIntelligence\frontend` and confirm the build succeeds with no CSS errors.

---

- [ ] 5. **Update ComponentsTest.tsx to demonstrate new functionality**
      
      The `ComponentsTest.tsx` page (at line 64-76) currently has one `MensionePickCard` example. Add two more examples below the existing one to demonstrate the new result state:
      
      **Example 1: Match with score, pending state (should show score + confidence)**
      ```tsx
      <MensionePickCard
        homeTeam="BARCELONA"
        awayTeam="REAL MADRID"
        marketName="Maç Sonucu"
        outcome="Ev Sahibi Kazanır"
        confidence={0.85}
        realOdds={1.95}
        isFavorite={false}
        onToggleFavorite={() => {}}
        inCombine={false}
        onToggleCombine={() => {}}
        skor={{ ev: 3, dep: 1 }}
        durum="pending"
      />
      ```
      
      **Example 2: Won match (should show score + WON badge)**
      ```tsx
      <MensionePickCard
        homeTeam="LIVERPOOL"
        awayTeam="ARSENAL"
        marketName="2.5+ Gol"
        outcome="Üst"
        confidence={0.72}
        realOdds={1.65}
        isFavorite={false}
        onToggleFavorite={() => {}}
        inCombine={false}
        onToggleCombine={() => {}}
        skor={{ ev: 4, dep: 2 }}
        durum="won"
      />
      ```
      
      **Example 3: Lost match (should show score + LOST badge)**
      ```tsx
      <MensionePickCard
        homeTeam="CHELSEA"
        awayTeam="MANCHESTER CITY"
        marketName="İlk Yarı 1.5+ Gol"
        outcome="Üst"
        confidence={0.68}
        realOdds={1.75}
        isFavorite={false}
        onToggleFavorite={() => {}}
        inCombine={false}
        onToggleCombine={() => {}}
        skor={{ ev: 0, dep: 1 }}
        durum="lost"
      />
      ```
      
      **Files:**
      - `c:\FootballIntelligence\frontend\src\pages\ComponentsTest.tsx`
      
      **Verify:**
      Run `npm run type-check` in `c:\FootballIntelligence\frontend` and confirm no TypeScript errors. Manually inspect the /components-test page in the browser to verify the visual display is correct.

---

- [ ] 6. **Run full frontend verification**
      
      Execute the complete frontend verification suite to ensure no regressions and the new functionality works correctly:
      
      **Commands:**
      ```powershell
      cd c:\FootballIntelligence\frontend
      npm run type-check
      npm run lint
      npm run build
      ```
      
      **Expected results:**
      - `type-check`: No TypeScript errors
      - `lint`: No linting errors or warnings
      - `build`: Successful production build with no errors
      
      If tests exist for MensionePickCard component, also run:
      ```powershell
      npm run test
      ```
      
      **Files:**
      - All frontend TypeScript and CSS files
      
      **Verify:**
      All commands complete successfully with exit code 0. Document exact test counts and results.

---

- [ ] 7. **Run backend verification (no backend changes, but verify no regression)**
      
      Although this change is frontend-only, verify that the backend still functions correctly:
      
      **Commands:**
      ```powershell
      cd c:\FootballIntelligence\backend
      python -m pytest -x
      ```
      
      **Expected result:**
      All backend tests pass with no failures.
      
      **Files:**
      - Backend test suite
      
      **Verify:**
      Backend tests pass. Document exact test counts and results. If tests fail, this indicates an environmental issue unrelated to this change — investigate separately.

---

- [ ] 8. **Update PROGRESS.md with implementation details**
      
      Append a new entry to `c:\FootballIntelligence\docs\PROGRESS.md` documenting:
      - Date and task description
      - Files modified (TSX, CSS, ComponentsTest.tsx)
      - New props added (`skor`, `durum`)
      - Verification commands run and their results (with actual numbers)
      - Visual confirmation that result states display correctly
      - Confirmation that no existing functionality was broken
      
      **Files:**
      - `c:\FootballIntelligence\docs\PROGRESS.md`
      
      **Verify:**
      Confirm the file was updated and the entry contains accurate information from the verification steps.

---

## Design Decisions

### Why default `durum` to `'pending'`?
Most cards in the system will be for upcoming/pending matches. Defaulting to `'pending'` reduces boilerplate in the majority of use cases.

### Why use `skor` with Turkish property names `ev`/`dep`?
Following the user's explicit specification. The component uses Turkish for user-facing labels but the original interface uses English. This hybrid approach (Turkish `skor` wrapper with Turkish properties) matches the user's data model.

### Why monospace font for score numbers?
Ensures consistent alignment and width for score display, which is a common pattern in sports UIs. The tabular-nums font variant is already used throughout the component.

### Why pill shape (9999px radius) for badges?
Matches modern UI conventions for status badges and creates clear visual distinction from the angular design of the rest of the card.

### Why not remove partner props?
After inspecting the component, no partner-related code exists. The user's request to remove partner functionality appears to be based on an outdated understanding or a different component. No work is needed.

---

## Verification Summary

This plan ensures:
1. Type safety through TypeScript type-check
2. Code quality through linting
3. Production readiness through build verification
4. No backend regression through pytest
5. Visual correctness through manual ComponentsTest inspection
6. Documentation through PROGRESS.md update

All verification uses actual project commands discovered during exploration (npm run type-check, npm run lint, npm run build, python -m pytest).
