import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLiveMatches } from '../api/client';
import type { LiveMatchesResponse } from '../api/types';
import { formatMatchStatus } from '../utils/formatters';
import './Live.css';

export function Live() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState<LiveMatchesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchLiveMatches() {
      try {
        setLoading(true);
        setError(null);
        const data = await getLiveMatches();
        
        if (mounted) {
          setMatches(data);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Canlı maçlar yüklenirken bir hata oluştu');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchLiveMatches();
    
    // Poll every 30 seconds
    const interval = setInterval(fetchLiveMatches, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleMatchClick = (matchId: string) => {
    navigate(`/matches/${matchId}`);
  };

  if (loading && !matches) {
    return (
      <div className="live-page">
        <div className="live-page__header">
          <h1 className="live-page__title">Canlı Maçlar</h1>
        </div>
        <div className="live-page__loading">Yükleniyor...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="live-page">
        <div className="live-page__header">
          <h1 className="live-page__title">Canlı Maçlar</h1>
        </div>
        <div className="live-page__error">{error}</div>
      </div>
    );
  }

  if (!matches || matches.matches.length === 0) {
    return (
      <div className="live-page">
        <div className="live-page__header">
          <h1 className="live-page__title">Canlı Maçlar</h1>
          <div className="live-page__subtitle">
            Şu anda canlı maç bulunmuyor
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="live-page">
      <div className="live-page__header">
        <h1 className="live-page__title">Canlı Maçlar</h1>
        <div className="live-page__subtitle">
          {matches.matches.length} canlı maç • {matches.provider_used ?? 'Unknown'}
        </div>
      </div>

      <div className="live-page__matches">
        {matches.matches.map((match) => (
          <div
            key={match.match_id}
            className="live-match-card"
            onClick={() => handleMatchClick(match.match_id)}
          >
            <div className="live-match-card__status">
              <span className="live-match-card__status-badge">
                {formatMatchStatus(match.status)}
              </span>
              {match.minute && (
                <span className="live-match-card__minute">{match.minute}'</span>
              )}
            </div>
            
            <div className="live-match-card__score">
              <div className="live-match-card__team">
                <span className="live-match-card__team-name">
                  {match.home_team}
                </span>
              </div>
              
              <div className="live-match-card__scoreboard">
                <span className="live-match-card__score-value">
                  {match.home_score}
                </span>
                <span className="live-match-card__score-separator">-</span>
                <span className="live-match-card__score-value">
                  {match.away_score}
                </span>
              </div>
              
              <div className="live-match-card__team">
                <span className="live-match-card__team-name">
                  {match.away_team}
                </span>
              </div>
            </div>

            <div className="live-match-card__quality">
              {match.data_quality_flags.has_xg && (
                <span className="live-match-card__quality-badge">xG</span>
              )}
              {match.data_quality_flags.has_events && (
                <span className="live-match-card__quality-badge">Events</span>
              )}
              {match.data_quality_flags.has_shots && (
                <span className="live-match-card__quality-badge">Shots</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="live-page__footer">
        <div className="live-page__provider-status">
          Toplam: {matches.data_quality.total_matches} maç
          {matches.data_quality.matches_with_xg > 0 && (
            <> • xG: {matches.data_quality.matches_with_xg}</>
          )}
        </div>
      </div>
    </div>
  );
}
