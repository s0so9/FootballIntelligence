/**
 * StatisticsComparison Component
 * 
 * Displays compact table comparing team statistics.
 * Shows real values when available, '--' when unavailable.
 * NEVER generates fake statistics.
 */

import type { MatchPredictionResponse } from '../../api/types'
import './StatisticsComparison.css'

interface StatisticsComparisonProps {
  /** Home team name */
  homeTeam: string
  /** Away team name */
  awayTeam: string
  /** Prediction data (contains xG and potentially other stats) */
  prediction: MatchPredictionResponse | null
}

interface StatRow {
  label: string
  homeValue: string | number
  awayValue: string | number
}

export default function StatisticsComparison({
  homeTeam,
  awayTeam,
  prediction
}: StatisticsComparisonProps) {
  // Build statistics rows - only include available data
  const stats: StatRow[] = []
  
  // Expected Goals (xG) - always available from prediction
  if (prediction) {
    stats.push({
      label: 'Beklenen Gol (xG)',
      homeValue: prediction.home_xg.toFixed(2),
      awayValue: prediction.away_xg.toFixed(2)
    })
  }
  
  // Placeholder rows for future data integration
  // Show '--' to indicate data is not yet available
  stats.push(
    { label: 'Şut', homeValue: '--', awayValue: '--' },
    { label: 'İsabetli Şut', homeValue: '--', awayValue: '--' },
    { label: 'Korner', homeValue: '--', awayValue: '--' },
    { label: 'Topa Sahip %', homeValue: '--', awayValue: '--' }
  )

  return (
    <div className="statistics-comparison">
      <h4 className="statistics-comparison__title">İstatistik Karşılaştırması</h4>
      
      <div className="stats-table">
        {/* Header row */}
        <div className="stats-table__header">
          <div className="stats-table__team-col">{homeTeam}</div>
          <div className="stats-table__stat-col">İstatistik</div>
          <div className="stats-table__team-col">{awayTeam}</div>
        </div>
        
        {/* Data rows */}
        {stats.map((stat, idx) => (
          <div key={idx} className="stats-table__row">
            <div className="stats-table__team-col stats-table__team-col--home">
              {stat.homeValue}
            </div>
            <div className="stats-table__stat-col">
              {stat.label}
            </div>
            <div className="stats-table__team-col stats-table__team-col--away">
              {stat.awayValue}
            </div>
          </div>
        ))}
      </div>
      
      {/* Note about unavailable data */}
      <div className="statistics-comparison__note">
        <span className="note-icon">ℹ️</span>
        <span className="note-text">
          Bazı istatistikler henüz mevcut değil. Veriler güncellendiğinde otomatik olarak gösterilecektir.
        </span>
      </div>
    </div>
  )
}
