/**
 * MensionePickCard Component
 * 
 * Main prediction card displaying MENSIONE PICK with strongest green glow.
 * Shows AI confidence and real odds separately (NEVER combined mathematically).
 * Includes favorite toggle (star icon) and combine checkbox.
 */

import AIConfidence from './AIConfidence'
import './MensionePickCard.css'

interface MensionePickCardProps {
  /** Home team name */
  homeTeam: string
  /** Away team name */
  awayTeam: string
  /** Market name (e.g., "İlk Yarı 0.5+ Gol") */
  marketName: string
  /** Outcome/selection (e.g., "Üst") */
  outcome: string
  /** AI confidence (0-1 or 0-100) - passed to AIConfidence component */
  confidence: number
  /** Real market odds (e.g., 1.82) - displayed separately from confidence */
  realOdds: number
  /** Whether this prediction is favorited */
  isFavorite: boolean
  /** Callback when favorite is toggled */
  onToggleFavorite: () => void
  /** Whether this prediction is in combine */
  inCombine: boolean
  /** Callback when combine is toggled */
  onToggleCombine: () => void
}

export default function MensionePickCard({
  homeTeam,
  awayTeam,
  marketName,
  outcome,
  confidence,
  realOdds,
  isFavorite,
  onToggleFavorite,
  inCombine,
  onToggleCombine
}: MensionePickCardProps) {
  return (
    <article className="mensione-pick-card">
      {/* Match header */}
      <div className="mensione-pick-card__header">
        <h3 className="mensione-pick-card__match-title">
          {homeTeam} vs {awayTeam}
        </h3>
        
        <button
          type="button"
          className="mensione-pick-card__favorite-button"
          onClick={onToggleFavorite}
          aria-label={isFavorite ? 'Favorilerden çıkar' : 'Favorilere ekle'}
          aria-pressed={isFavorite}
        >
          {isFavorite ? '⭐' : '☆'}
        </button>
      </div>
      
      {/* MENSIONE PICK badge - strongest green glow */}
      <div className="mensione-pick-badge" aria-label="MENSIONE seçimi">
        <span className="mensione-pick-badge__icon">🟢</span>
        <span className="mensione-pick-badge__text">MENSIONE PICK</span>
      </div>
      
      {/* Market and outcome */}
      <div className="mensione-pick-card__market">
        <div className="mensione-pick-card__market-name">{marketName}</div>
        <div className="mensione-pick-card__outcome">{outcome}</div>
      </div>
      
      {/* AI Confidence - separate component */}
      <div className="mensione-pick-card__confidence">
        <AIConfidence 
          confidence={confidence} 
          size="sm"
          showPercentage={true}
          showLevel={true}
          showLabel={true}
        />
      </div>
      
      {/* Real odds - displayed SEPARATELY from confidence */}
      <div className="mensione-pick-card__odds-section">
        <div className="mensione-pick-card__odds-label">Oran</div>
        <div className="mensione-pick-card__odds-value">{realOdds.toFixed(2)}</div>
      </div>
      
      {/* Combine checkbox */}
      <div className="mensione-pick-card__footer">
        <label className="mensione-pick-card__combine-label">
          <input
            type="checkbox"
            className="mensione-pick-card__combine-checkbox"
            checked={inCombine}
            onChange={onToggleCombine}
            aria-label="Kombine ekle"
          />
          <span className="mensione-pick-card__combine-text">Kombine Ekle</span>
        </label>
      </div>
    </article>
  )
}
