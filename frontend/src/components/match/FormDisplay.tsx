/**
 * FormDisplay Component
 * 
 * Displays recent form as W/D/L indicators for last 5 matches.
 * Shows empty state if no form data available.
 */

import './FormDisplay.css'

export type FormResult = 'W' | 'D' | 'L'

interface FormMatch {
  result: FormResult
  score?: string
  opponent?: string
  date?: string
}

interface FormDisplayProps {
  /** Team name */
  teamName: string
  /** Recent match results (newest first) */
  matches?: FormMatch[]
}

export default function FormDisplay({
  teamName,
  matches
}: FormDisplayProps) {
  // Empty state - no form data available
  if (!matches || matches.length === 0) {
    return (
      <div className="form-display form-display--empty">
        <h5 className="form-display__title">{teamName} - Son Performans</h5>
        <div className="form-display__empty-state">
          <span className="empty-state-icon">📊</span>
          <span className="empty-state-text">Form verisi mevcut değil</span>
        </div>
      </div>
    )
  }

  // Take last 5 matches
  const recentMatches = matches.slice(0, 5)

  return (
    <div className="form-display">
      <h5 className="form-display__title">{teamName} - Son Performans</h5>
      
      <div className="form-indicators">
        {recentMatches.map((match, idx) => (
          <div
            key={idx}
            className={`form-indicator form-indicator--${match.result.toLowerCase()}`}
            title={match.opponent ? `${match.result} vs ${match.opponent}` : match.result}
            aria-label={`${match.result === 'W' ? 'Galibiyet' : match.result === 'D' ? 'Beraberlik' : 'Mağlubiyet'}`}
          >
            {match.result}
          </div>
        ))}
      </div>
      
      {/* Optional: Show match details if available */}
      {recentMatches.some(m => m.score || m.opponent) && (
        <div className="form-details">
          {recentMatches.map((match, idx) => (
            match.opponent || match.score ? (
              <div key={idx} className="form-detail-item">
                {match.opponent && <span className="form-detail-opponent">{match.opponent}</span>}
                {match.score && <span className="form-detail-score">{match.score}</span>}
              </div>
            ) : null
          ))}
        </div>
      )}
    </div>
  )
}
