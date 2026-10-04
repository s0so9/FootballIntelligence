import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getUpcomingMatches } from '../api';
import type { MatchResponse } from '../api/types';
import { formatTeamName, formatCompetitionName, formatMatchDateTime, formatMatchStatus } from '../utils/formatters';
import './Matches.css';

export function Matches() {
  const [matches, setMatches] = useState<MatchResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevelopmentData, setIsDevelopmentData] = useState(false);

  useEffect(() => {
    async function fetchMatches() {
      try {
        setLoading(true);
        setError(null);

        const response = await getUpcomingMatches(14); // Next 14 days
        setMatches(response.matches);
        setIsDevelopmentData(response.is_development_data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Maçlar yüklenirken bir hata oluştu');
      } finally {
        setLoading(false);
      }
    }

    fetchMatches();
  }, []);

  if (loading) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Maçlar</h1>
          <p className="page-subtitle">Yaklaşan maçlar ve tahminler</p>
        </div>
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Maçlar yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Maçlar</h1>
          <p className="page-subtitle">Yaklaşan maçlar ve tahminler</p>
        </div>
        <div className="error-state">
          <p className="error-message">{error}</p>
          <p className="error-hint">Backend sunucusunun çalıştığından emin olun.</p>
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Maçlar</h1>
          <p className="page-subtitle">Yaklaşan maçlar ve tahminler</p>
        </div>
        <div className="empty-state">
          <div className="empty-icon">⚽</div>
          <p className="empty-title">Yaklaşan maç bulunamadı</p>
          <p className="empty-description">
            Önümüzdeki 14 günde planlanmış maç bulunmamaktadır.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Maçlar</h1>
        <p className="page-subtitle">
          Yaklaşan maçlar ve tahminler
          {isDevelopmentData && (
            <span className="dev-badge">Geliştirme Verisi</span>
          )}
        </p>
      </div>

      <div className="matches-list">
        {matches.map((match) => {
          const dateTime = formatMatchDateTime(match.scheduled_at);

          return (
            <Link
              key={match.id}
              to={`/matches/${match.id}`}
              className="match-card"
            >
              <div className="match-card__header">
                <div className="match-card__competition">
                  {formatCompetitionName(match.competition_id)}
                  {match.round && ` - ${match.round}. Hafta`}
                </div>
                <span className={`match-status match-status--${match.status}`}>
                  {formatMatchStatus(match.status)}
                </span>
              </div>

              <div className="match-card__body">
                <div className="match-card__datetime">
                  <div className="match-date">{dateTime.date}</div>
                  <div className="match-time">{dateTime.time}</div>
                </div>

                <div className="match-card__teams">
                  <div className="team team--home">
                    <span className="team-name">{formatTeamName(match.home_team_id)}</span>
                  </div>

                  <div className="match-vs">
                    {match.home_score !== null && match.away_score !== null ? (
                      <div className="match-score">
                        {match.home_score} - {match.away_score}
                      </div>
                    ) : (
                      <span className="vs-text">vs</span>
                    )}
                  </div>

                  <div className="team team--away">
                    <span className="team-name">{formatTeamName(match.away_team_id)}</span>
                  </div>
                </div>

                {match.status === 'scheduled' && (
                  <div className="match-card__indicator">
                    <span className="prediction-indicator">
                      📊 Tahmin Mevcut
                    </span>
                  </div>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
