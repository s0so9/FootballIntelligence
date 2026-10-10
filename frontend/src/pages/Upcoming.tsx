import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getMatches, getCompetitions } from '../api';
import type { CompetitionResponse } from '../api/types';
import { normalizeMatches, type NormalizedMatch } from '../utils/matchNormalizer';
import { formatCompetitionName, formatMatchDateTime, formatMatchStatus } from '../utils/formatters';
import { normalizeCompetitionName } from '../utils/popularCompetitions';
import './Matches.css';

export function Upcoming() {
  const [competitions, setCompetitions] = useState<CompetitionResponse[]>([]);
  const [matches, setMatches] = useState<NormalizedMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevelopmentData, setIsDevelopmentData] = useState(false);

  // Load all upcoming matches from all competitions
  useEffect(() => {
    let isMounted = true;

    async function fetchUpcomingMatches() {
      try {
        setLoading(true);
        setError(null);

        // Fetch competitions first for display names
        const competitionsResponse = await getCompetitions();
        
        if (!isMounted) return;
        
        setCompetitions(competitionsResponse.competitions);

        // Use UTC date range for filtering - next 30 days for more matches
        const today = new Date();
        const fromDate = formatDateForAPI(today);
        const futureDate = new Date(today);
        futureDate.setDate(futureDate.getDate() + 30); // Increased to 30 days
        const toDate = formatDateForAPI(futureDate);

        // Fetch upcoming matches with broader date range
        const matchesResponse = await getMatches({
          from_date: fromDate,
          to_date: toDate,
          status: 'scheduled',
        });
        
        if (!isMounted) return;

        const normalizedMatches = normalizeMatches(matchesResponse.matches);
        
        // Filter for truly upcoming matches - scheduled status AND future time
        const now = new Date();
        const upcomingMatches = normalizedMatches.filter(match => {
          // Must be scheduled status
          if (match.status !== 'scheduled') return false;
          
          // Must be in the future (Istanbul timezone consideration)
          const matchTime = new Date(match.scheduledAt);
          return matchTime > now;
        });
        
        // Sort by kick-off time (earliest first)
        upcomingMatches.sort((a, b) => 
          new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()
        );
        
        setMatches(upcomingMatches);
        setIsDevelopmentData(matchesResponse.is_development_data);
      } catch (err) {
        if (!isMounted) return;
        console.error('Error loading upcoming matches:', err);
        setError(err instanceof Error ? err.message : 'Yaklaşan maçlar yüklenirken bir hata oluştu');
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchUpcomingMatches();

    return () => {
      isMounted = false;
    };
  }, []);

  // Helper function
  function formatDateForAPI(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  if (loading) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Yaklaşan Maçlar</h1>
          <p className="page-subtitle">Önümüzdeki 7 günün tüm maçları</p>
        </div>
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Yaklaşan maçlar yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Yaklaşan Maçlar</h1>
          <p className="page-subtitle">Önümüzdeki 7 günün tüm maçları</p>
        </div>
        <div className="error-state">
          <p className="error-message">{error}</p>
          <p className="error-hint">Backend sunucusunun çalıştığından emin olun.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Yaklaşan Maçlar</h1>
        <p className="page-subtitle">
          Önümüzdeki 7 günün tüm maçları
          {isDevelopmentData && (
            <span className="dev-badge">Geliştirme Verisi</span>
          )}
        </p>
      </div>

      {matches.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">⚽</div>
          <p className="empty-title">Yaklaşan maç bulunamadı</p>
          <p className="empty-description">
            Önümüzdeki 7 günde planlanmış maç bulunmamaktadır.
          </p>
        </div>
      )}

      {matches.length > 0 && (
        <div className="matches-list">
          {(() => {
            // Group matches by competition
            const matchesByCompetition = matches.reduce((groups, match) => {
              const competition = competitions.find(c => c.id === match.competitionId);
              let competitionName: string;
              
              if (competition) {
                const normalizedName = normalizeCompetitionName(competition.name);
                competitionName = normalizedName || competition.name;
              } else if (/^\d+$/.test(match.competitionId)) {
                competitionName = 'Bilinmeyen lig';
              } else {
                competitionName = formatCompetitionName(match.competitionId);
              }
              
              if (!groups[competitionName]) {
                groups[competitionName] = [];
              }
              groups[competitionName].push(match);
              return groups;
            }, {} as Record<string, NormalizedMatch[]>);

            // Sort competitions by name and render grouped matches
            return Object.keys(matchesByCompetition)
              .sort((a, b) => a.localeCompare(b, 'tr'))
              .map(competitionName => (
                <div key={competitionName} className="competition-group">
                  <h3 className="competition-group__title">
                    {competitionName}
                    <span className="competition-group__count">
                      ({matchesByCompetition[competitionName].length} maç)
                    </span>
                  </h3>
                  
                  <div className="competition-group__matches">
                    {matchesByCompetition[competitionName].map((match) => {
                      const dateTime = formatMatchDateTime(match.scheduledAt);

                      return (
                        <Link
                          key={match.id}
                          to={`/matches/${match.id}`}
                          className="match-card"
                        >
                          <div className="match-card__header">
                            <div className="match-card__competition">
                              {competitionName}
                              {match.round && ` - ${match.round}. Hafta`}
                            </div>
                            <span className={`match-status match-status--${match.status}`}>
                              {formatMatchStatus(match.status as import('../api/types').MatchStatus)}
                            </span>
                          </div>

                          <div className="match-card__body">
                            <div className="match-card__datetime">
                              <div className="match-date">{dateTime.date}</div>
                              <div className="match-time">{dateTime.time}</div>
                            </div>

                            <div className="match-card__teams">
                              <div className="team team--home">
                                <span className="team-name">{match.homeTeam.name}</span>
                              </div>

                              <div className="match-vs">
                                <span className="vs-text">vs</span>
                              </div>

                              <div className="team team--away">
                                <span className="team-name">{match.awayTeam.name}</span>
                              </div>
                            </div>

                            <div className="match-card__indicator">
                              <span className="prediction-indicator">
                                📊 Tahmin Mevcut
                              </span>
                            </div>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ));
          })()}
        </div>
      )}
    </div>
  );
}