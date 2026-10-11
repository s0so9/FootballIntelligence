import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getLiveMatches, getMatch } from '../api/client';
import type { LiveMatchesResponse, MatchResponse } from '../api/types';
import { formatMatchStatus } from '../utils/formatters';
import FieldOverheadView from '../components/live/FieldOverheadView';
import MatchStatistics from '../components/live/MatchStatistics';
import AudioSettings from '../components/AudioSettings';
import { playGoal } from '../services/audioService';
import './Live.css';

export function Live() {
  const navigate = useNavigate();
  const { matchId } = useParams();
  const [matches, setMatches] = useState<LiveMatchesResponse | null>(null);
  const [matchDetail, setMatchDetail] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [showAudioSettings, setShowAudioSettings] = useState(false);
  const [lastEventCount, setLastEventCount] = useState<number>(0);

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
    
    // Poll every 30 seconds while the app is visible
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchLiveMatches();
      }
    }, 30000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && mounted) {
        fetchLiveMatches();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      mounted = false;
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  // Fetch match details when matchId changes
  useEffect(() => {
    if (!matchId) {
      setMatchDetail(null);
      setDetailError(null);
      return;
    }

    let mounted = true;

    async function fetchMatchDetail() {
      try {
        setLoadingDetail(true);
        setDetailError(null);
        const data = await getMatch(matchId!); // Non-null assertion since we check above
        
        if (mounted) {
          setMatchDetail(data.match);
          
          // Check for new events and play audio
          checkForNewEvents(data.match);
        }
      } catch (err) {
        if (mounted) {
          setDetailError(err instanceof Error ? err.message : 'Maç detayları yüklenirken bir hata oluştu');
          setMatchDetail(null);
        }
      } finally {
        if (mounted) {
          setLoadingDetail(false);
        }
      }
    }

    fetchMatchDetail();
    
    // Poll match details every 10 seconds while visible
    const detailInterval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchMatchDetail();
      }
    }, 10000);

    return () => {
      mounted = false;
      clearInterval(detailInterval);
    };
  }, [matchId]);

  // Function to check for new events and trigger audio
  const checkForNewEvents = (match: MatchResponse) => {
    // In a real implementation, this would compare with previous match state
    // to detect new goals, cards, etc. For now, we'll simulate based on score changes
    
    if (!matches) return;
    
    const liveMatch = matches.matches.find(m => m.match_id === match.id);
    if (!liveMatch) return;
    
    // Simple event detection based on score changes
    const totalGoals = (match.home_score || 0) + (match.away_score || 0);
    
    if (totalGoals > lastEventCount) {
      // New goal detected
      console.log('New goal detected!');
      playGoal(); // Play goal sound
      setLastEventCount(totalGoals);
    }
  };

  const handleMatchClick = (matchId: string) => {
    navigate(`/live/${matchId}`);
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
        <div className="live-page__error">
          <p>{error}</p>
          <button
            type="button"
            className="live-page__back-btn"
            onClick={() => window.location.reload()}
          >
            Tekrar dene
          </button>
        </div>
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

  // Show field view if specific match is selected
  if (matchId) {
    // Check if we have detail data
    const selectedMatch = matchDetail || matches?.matches.find(m => m.match_id === matchId);
    
    if (loadingDetail) {
      return (
        <div className="live-page">
          <div className="live-page__header">
            <button 
              className="live-page__back-btn"
              onClick={() => navigate('/live')}
            >
              ← Tüm Canlı Maçlar
            </button>
            <h1 className="live-page__title">Maç Detayları</h1>
          </div>
          <div className="live-page__loading">Detaylar yükleniyor...</div>
        </div>
      );
    }

    if (detailError) {
      return (
        <div className="live-page">
          <div className="live-page__header">
            <button 
              className="live-page__back-btn"
              onClick={() => navigate('/live')}
            >
              ← Tüm Canlı Maçlar
            </button>
            <h1 className="live-page__title">Hata</h1>
          </div>
          <div className="live-page__error">{detailError}</div>
        </div>
      );
    }

    if (!selectedMatch) {
      return (
        <div className="live-page">
          <div className="live-page__header">
            <button 
              className="live-page__back-btn"
              onClick={() => navigate('/live')}
            >
              ← Tüm Canlı Maçlar
            </button>
            <h1 className="live-page__title">Maç Bulunamadı</h1>
          </div>
          <div className="live-page__error">Bu maç bulunamadı veya artık canlı değil.</div>
        </div>
      );
    }

    // Convert mock events for demonstration
    const mockEvents = [
      {
        id: 'goal_1',
        type: 'goal' as const,
        minute: 23,
        team: 'home' as const,
        player: (typeof selectedMatch.home_team === 'string' ? selectedMatch.home_team : selectedMatch.home_team?.name || 'Home Team') + ' Oyuncusu',
        coordinates: { x: 102, y: 34 }, // Near goal
        description: 'Gol'
      },
      {
        id: 'shot_1',
        type: 'shot' as const,
        minute: 45,
        team: 'away' as const,
        player: (typeof selectedMatch.away_team === 'string' ? selectedMatch.away_team : selectedMatch.away_team?.name || 'Away Team') + ' Oyuncusu',
        coordinates: { x: 85, y: 42 }, // Shot from distance
        description: 'Şut'
      }
    ];

    // Get team names - prefer full match data if available, ensure they're strings
    const homeTeamName = matchDetail?.home_team?.name 
      || (typeof selectedMatch.home_team === 'string' ? selectedMatch.home_team : selectedMatch.home_team?.name)
      || 'Ev Sahibi';
    const awayTeamName = matchDetail?.away_team?.name 
      || (typeof selectedMatch.away_team === 'string' ? selectedMatch.away_team : selectedMatch.away_team?.name) 
      || 'Deplasman';

    return (
      <div className="live-page">
        <div className="live-page__header">
          <button 
            className="live-page__back-btn"
            onClick={() => navigate('/live')}
          >
            ← Tüm Canlı Maçlar
          </button>
          <div className="live-page__title-section">
            <h1 className="live-page__title">
              {homeTeamName} vs {awayTeamName}
            </h1>
            <button 
              className="live-page__audio-btn"
              onClick={() => setShowAudioSettings(true)}
              title="Ses Ayarları"
              aria-label="Ses Ayarları"
            >
              🔊
            </button>
          </div>
          <div className="live-page__subtitle">
            {selectedMatch.home_score}-{selectedMatch.away_score} • {selectedMatch.minute && `${selectedMatch.minute}'`}
          </div>
        </div>

        <FieldOverheadView
          events={mockEvents}
          dataQuality={{
            has_events: ('data_quality_flags' in selectedMatch) ? selectedMatch.data_quality_flags.has_events : false,
            has_shot_coordinates: ('data_quality_flags' in selectedMatch) ? selectedMatch.data_quality_flags.has_shots : false,
            has_player_positions: ('data_quality_flags' in selectedMatch) ? selectedMatch.data_quality_flags.has_player_positions : false,
            has_ball_tracking: ('data_quality_flags' in selectedMatch) ? selectedMatch.data_quality_flags.has_ball_tracking : false,
          }}
          homeTeam={homeTeamName}
          awayTeam={awayTeamName}
        />

        {/* Match Statistics - only show for full match detail */}
        {matchDetail && (
          <MatchStatistics
            homeStats={matchDetail.home_statistics}
            awayStats={matchDetail.away_statistics}
            homeTeam={homeTeamName}
            awayTeam={awayTeamName}
          />
        )}

        {/* Match details */}
        <div className="live-match-details">
          <div className="live-match-details__section">
            <h3>Maç Bilgileri</h3>
            <div className="live-match-details__info">
              <div>Durum: {formatMatchStatus(selectedMatch.status)}</div>
              {selectedMatch.minute && <div>Dakika: {selectedMatch.minute}'</div>}
              <div>Skor: {selectedMatch.home_score}-{selectedMatch.away_score}</div>
              {matchDetail?.scheduled_at && (
                <div>Tarih: {new Date(matchDetail.scheduled_at).toLocaleString('tr-TR')}</div>
              )}
            </div>
          </div>
          
          <div className="live-match-details__section">
            <h3>Veri Kalitesi</h3>
            <div className="live-match-details__quality">
              {('data_quality_flags' in selectedMatch) && Object.entries(selectedMatch.data_quality_flags).map(([key, value]) => (
                <span key={key} className={`quality-flag ${value ? 'available' : 'unavailable'}`}>
                  {value ? '✓' : '✗'} {key.replace('has_', '').replace('_', ' ')}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="live-page">
      <div className="live-page__header">
        <div className="live-page__title-section">
          <h1 className="live-page__title">Canlı Maçlar</h1>
          <button 
            className="live-page__audio-btn"
            onClick={() => setShowAudioSettings(true)}
            title="Ses Ayarları"
            aria-label="Ses Ayarları"
          >
            🔊
          </button>
        </div>
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

      {/* Audio Settings Modal */}
      <AudioSettings
        isOpen={showAudioSettings}
        onClose={() => setShowAudioSettings(false)}
      />
    </div>
  );
}
