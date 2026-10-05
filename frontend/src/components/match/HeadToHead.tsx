/**
 * HeadToHead Component
 * 
 * Displays recent head-to-head meetings between two teams.
 * Shows empty state if no H2H data available.
 */

import './HeadToHead.css'

interface H2HMatch {
  date: string
  homeTeam: string
  awayTeam: string
  score: string
  competition?: string
}

interface HeadToHeadProps {
  /** Home team name */
  homeTeam: string
  /** Away team name */
  awayTeam: string
  /** Recent head-to-head matches */
  matches?: H2HMatch[]
}

export default function HeadToHead({
  homeTeam,
  awayTeam,
  matches
}: HeadToHeadProps) {
  // Empty state - no H2H data available
  if (!matches || matches.length === 0) {
    return (
      <div className="head-to-head head-to-head--empty">
        <h5 className="head-to-head__title">Karşılıklı Geçmiş</h5>
        <div className="head-to-head__empty-state">
          <span className="empty-state-icon">🔄</span>
          <span className="empty-state-text">
            {homeTeam} ve {awayTeam} arasında geçmiş maç verisi mevcut değil
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="head-to-head">
      <h5 className="head-to-head__title">
        Karşılıklı Geçmiş ({homeTeam} vs {awayTeam})
      </h5>
      
      <div className="h2h-matches">
        {matches.map((match, idx) => (
          <div key={idx} className="h2h-match">
            <div className="h2h-match__date">
              {new Date(match.date).toLocaleDateString('tr-TR', {
                day: 'numeric',
                month: 'short',
                year: 'numeric'
              })}
            </div>
            
            <div className="h2h-match__teams">
              <span className="h2h-match__team">{match.homeTeam}</span>
              <span className="h2h-match__separator">vs</span>
              <span className="h2h-match__team">{match.awayTeam}</span>
            </div>
            
            <div className="h2h-match__score">{match.score}</div>
            
            {match.competition && (
              <div className="h2h-match__competition">{match.competition}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
