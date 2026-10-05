/**
 * GeneralAnalysis Component
 * 
 * Displays general match analysis including primary MENSIONE PICK,
 * predicted score, 1X2 probabilities, xG, BTTS, and key indicators.
 */

import MensionePickCard from '../predictions/MensionePickCard'
import ProbabilityDisplay from '../common/ProbabilityDisplay'
import type { MatchPredictionResponse, MatchResponse } from '../../api/types'
import './GeneralAnalysis.css'

interface GeneralAnalysisProps {
  /** Match prediction data */
  prediction: MatchPredictionResponse
  /** Match data */
  match: MatchResponse
  /** Home team name (formatted) */
  homeTeam: string
  /** Away team name (formatted) */
  awayTeam: string
  /** Whether this match is favorited */
  isFavorite: boolean
  /** Callback when favorite is toggled */
  onToggleFavorite: () => void
  /** Whether this match is in combine */
  inCombine: boolean
  /** Callback when combine is toggled */
  onToggleCombine: () => void
}

/**
 * Parse pick_market string to Turkish market name and outcome
 * Examples: "HOME" -> {market: "Maç Sonucu", outcome: "Ev Sahibi"}
 */
function parsePickMarket(pickMarket: string): { market: string; outcome: string } {
  const upper = pickMarket.toUpperCase().trim()
  
  if (upper === 'HOME') return { market: 'Maç Sonucu', outcome: 'Ev Sahibi Kazanır' }
  if (upper === 'DRAW') return { market: 'Maç Sonucu', outcome: 'Beraberlik' }
  if (upper === 'AWAY') return { market: 'Maç Sonucu', outcome: 'Deplasman Kazanır' }
  if (upper === 'BTTS YES') return { market: 'Karşılıklı Gol', outcome: 'Evet' }
  if (upper === 'BTTS NO') return { market: 'Karşılıklı Gol', outcome: 'Hayır' }
  if (upper.startsWith('OVER ')) {
    const line = upper.replace('OVER ', '')
    return { market: `Üst/Alt ${line}`, outcome: 'Üst' }
  }
  if (upper.startsWith('UNDER ')) {
    const line = upper.replace('UNDER ', '')
    return { market: `Üst/Alt ${line}`, outcome: 'Alt' }
  }
  
  // Fallback: return as-is
  return { market: pickMarket, outcome: '' }
}

export default function GeneralAnalysis({
  prediction,
  homeTeam,
  awayTeam,
  isFavorite,
  onToggleFavorite,
  inCombine,
  onToggleCombine
}: GeneralAnalysisProps) {
  const { mensione_pick } = prediction
  
  // Parse MENSIONE pick if available
  let mensioneMarket = ''
  let mensioneOutcome = ''
  if (mensione_pick) {
    const parsed = parsePickMarket(mensione_pick.pick_market)
    mensioneMarket = parsed.market
    mensioneOutcome = parsed.outcome
  }

  return (
    <div className="general-analysis">
      {/* Primary MENSIONE PICK - Prominent placement at top */}
      {mensione_pick && (
        <section className="general-analysis__primary-pick">
          <MensionePickCard
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            marketName={mensioneMarket}
            outcome={mensioneOutcome}
            confidence={mensione_pick.confidence_score}
            realOdds={mensione_pick.fair_odds}
            isFavorite={isFavorite}
            onToggleFavorite={onToggleFavorite}
            inCombine={inCombine}
            onToggleCombine={onToggleCombine}
          />
        </section>
      )}

      {/* Predicted Score */}
      {prediction.predicted_score && (
        <section className="general-analysis__predicted-score">
          <h4 className="general-analysis__section-title">Tahmini Skor</h4>
          <div className="predicted-score-display">
            {prediction.predicted_score}
          </div>
        </section>
      )}

      {/* 1X2 Probabilities */}
      <section className="general-analysis__probabilities">
        <h4 className="general-analysis__section-title">Maç Sonucu Olasılıkları</h4>
        <div className="probabilities-grid">
          <div className="probability-outcome">
            <div className="probability-outcome__label">{homeTeam} Kazanır</div>
            <ProbabilityDisplay 
              probability={prediction.home_win_probability} 
              large={true}
              showIcon={true}
            />
          </div>
          <div className="probability-outcome">
            <div className="probability-outcome__label">Beraberlik</div>
            <ProbabilityDisplay 
              probability={prediction.draw_probability} 
              large={true}
              showIcon={true}
            />
          </div>
          <div className="probability-outcome">
            <div className="probability-outcome__label">{awayTeam} Kazanır</div>
            <ProbabilityDisplay 
              probability={prediction.away_win_probability} 
              large={true}
              showIcon={true}
            />
          </div>
        </div>
      </section>

      {/* Expected Goals (xG) */}
      <section className="general-analysis__xg">
        <h4 className="general-analysis__section-title">Beklenen Goller (xG)</h4>
        <div className="xg-display">
          <div className="xg-team xg-team--home">
            <div className="xg-team__name">{homeTeam}</div>
            <div className="xg-team__value">{prediction.home_xg.toFixed(2)}</div>
          </div>
          <div className="xg-separator">-</div>
          <div className="xg-team xg-team--away">
            <div className="xg-team__value">{prediction.away_xg.toFixed(2)}</div>
            <div className="xg-team__name">{awayTeam}</div>
          </div>
        </div>
      </section>

      {/* BTTS Probability */}
      <section className="general-analysis__btts">
        <h4 className="general-analysis__section-title">Karşılıklı Gol (BTTS)</h4>
        <div className="btts-display">
          <div className="btts-outcome">
            <span className="btts-outcome__label">Evet</span>
            <ProbabilityDisplay 
              probability={prediction.btts_probability} 
              large={false}
              showIcon={false}
            />
          </div>
          <div className="btts-outcome">
            <span className="btts-outcome__label">Hayır</span>
            <ProbabilityDisplay 
              probability={1 - prediction.btts_probability} 
              large={false}
              showIcon={false}
            />
          </div>
        </div>
      </section>

      {/* Key Indicators from reasoning */}
      {mensione_pick?.reasoning_factors && mensione_pick.reasoning_factors.length > 0 && (
        <section className="general-analysis__key-indicators">
          <h4 className="general-analysis__section-title">Önemli Göstergeler</h4>
          <ul className="key-indicators-list">
            {mensione_pick.reasoning_factors.slice(0, 5).map((factor, idx) => (
              <li key={idx} className="key-indicator">
                <span className="key-indicator__icon">→</span>
                <span className="key-indicator__text">{factor}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
