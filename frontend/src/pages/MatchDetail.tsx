import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getMatch, getMatchPrediction } from '../api';
import type { MatchResponse, MatchPredictionResponse, MarketAnalysisResponse } from '../api/types';
import { 
  formatTeamName, 
  formatCompetitionName, 
  formatMatchDateTime,
  formatMatchStatus 
} from '../utils/formatters';
import ProbabilityDisplay from '../components/common/ProbabilityDisplay';
import ConfidenceIndicator from '../components/common/ConfidenceIndicator';
import ValueIndicator from '../components/common/ValueIndicator';
import './MatchDetail.css';

export function MatchDetail() {
  const { id } = useParams<{ id: string }>();
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [prediction, setPrediction] = useState<MatchPredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevelopmentData, setIsDevelopmentData] = useState(false);

  useEffect(() => {
    async function fetchMatchData() {
      if (!id) {
        setError('Geçersiz maç ID');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch match details
        const matchResponse = await getMatch(id);
        setMatch(matchResponse.match);
        setIsDevelopmentData(matchResponse.is_development_data);

        // Fetch prediction if match is scheduled
        if (matchResponse.match.status === 'scheduled') {
          try {
            const predictionResponse = await getMatchPrediction(id);
            setPrediction(predictionResponse);
          } catch (predErr) {
            // Prediction might not be available - this is okay
            console.warn('Prediction not available:', predErr);
            setPrediction(null);
          }
        }
      } catch (err) {
        if (err instanceof Error && err.message.includes('404')) {
          setError('Maç bulunamadı');
        } else {
          setError(err instanceof Error ? err.message : 'Maç verileri yüklenirken bir hata oluştu');
        }
      } finally {
        setLoading(false);
      }
    }

    fetchMatchData();
  }, [id]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Maç detayları yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="page-container">
        <div className="error-state">
          <p className="error-message">{error || 'Maç bulunamadı'}</p>
          <Link to="/matches" className="back-link">← Maçlara Dön</Link>
        </div>
      </div>
    );
  }

  const dateTime = formatMatchDateTime(match.scheduled_at);
  const homeTeam = formatTeamName(match.home_team_id);
  const awayTeam = formatTeamName(match.away_team_id);
  const competition = formatCompetitionName(match.competition_id);

  // Find market analysis for different market types
  const findMarket = (marketType: string, line?: number): MarketAnalysisResponse | undefined => {
    if (!prediction?.market_analysis) return undefined;
    return prediction.market_analysis.find(m => 
      m.market_type === marketType && 
      (line === undefined || m.line === line)
    );
  };

  const matchResultMarket = findMarket('match_result');
  const bttsMarket = findMarket('btts');
  const over25Market = findMarket('over_under', 2.5);
  const over35Market = findMarket('over_under', 3.5);

  return (
    <div className="page-container">
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link to="/matches" className="breadcrumb-link">Maçlar</Link>
        <span className="breadcrumb-separator">›</span>
        <span className="breadcrumb-current">Maç Detayı</span>
      </div>

      {/* Match Header */}
      <div className="match-detail-header">
        <div className="match-detail-header__info">
          <div className="match-competition">
            {competition}
            {match.round && ` - ${match.round}. Hafta`}
            {isDevelopmentData && (
              <span className="dev-badge">Geliştirme Verisi</span>
            )}
          </div>
          <div className="match-datetime">
            {dateTime.full}
          </div>
        </div>
        <span className={`match-status match-status--${match.status}`}>
          {formatMatchStatus(match.status)}
        </span>
      </div>

      {/* Match Teams */}
      <div className="match-teams-section">
        <div className="team-display team-display--home">
          <div className="team-display__name">{homeTeam}</div>
          {match.home_score !== null && (
            <div className="team-display__score">{match.home_score}</div>
          )}
        </div>

        <div className="match-vs">
          {match.home_score === null && match.away_score === null ? (
            <span className="vs-text">VS</span>
          ) : (
            <span className="score-separator">-</span>
          )}
        </div>

        <div className="team-display team-display--away">
          {match.away_score !== null && (
            <div className="team-display__score">{match.away_score}</div>
          )}
          <div className="team-display__name">{awayTeam}</div>
        </div>
      </div>

      {/* Prediction Section */}
      {match.status === 'scheduled' && (
        <div className="prediction-section">
          <h2 className="section-title">Tahmin Analizi</h2>

          {!prediction ? (
            <div className="info-state">
              <div className="info-icon">ℹ️</div>
              <p className="info-title">Tahmin mevcut değil</p>
              <p className="info-description">
                Bu maç için tahmin verisi henüz oluşturulmadı veya yeterli veri bulunmamaktadır.
              </p>
            </div>
          ) : !prediction.easy_match?.data_sufficient ? (
            <div className="warning-state">
              <div className="warning-icon">⚠️</div>
              <p className="warning-title">Yetersiz veri</p>
              <p className="warning-description">
                Tahmin oluşturuldu ancak veri kalitesi optimal değil. Sonuçlar daha az güvenilir olabilir.
              </p>
            </div>
          ) : null}

          {prediction && (
            <>
              {/* 1X2 Probabilities */}
              <div className="prediction-card">
                <h3 className="prediction-card__title">Maç Sonucu (1X2)</h3>
                <div className="prediction-grid prediction-grid--three">
                  <div className="prediction-outcome">
                    <div className="prediction-outcome__label">{homeTeam} Kazanır</div>
                    <ProbabilityDisplay probability={prediction.home_win_probability} />
                    {matchResultMarket?.outcomes[0] && (
                      <div className="prediction-outcome__odds">
                        Adil Oran: {matchResultMarket.outcomes[0].fair_odds.toFixed(2)}
                      </div>
                    )}
                  </div>
                  <div className="prediction-outcome">
                    <div className="prediction-outcome__label">Beraberlik</div>
                    <ProbabilityDisplay probability={prediction.draw_probability} />
                    {matchResultMarket?.outcomes[1] && (
                      <div className="prediction-outcome__odds">
                        Adil Oran: {matchResultMarket.outcomes[1].fair_odds.toFixed(2)}
                      </div>
                    )}
                  </div>
                  <div className="prediction-outcome">
                    <div className="prediction-outcome__label">{awayTeam} Kazanır</div>
                    <ProbabilityDisplay probability={prediction.away_win_probability} />
                    {matchResultMarket?.outcomes[2] && (
                      <div className="prediction-outcome__odds">
                        Adil Oran: {matchResultMarket.outcomes[2].fair_odds.toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Expected Goals */}
              <div className="prediction-card">
                <h3 className="prediction-card__title">Beklenen Goller (xG)</h3>
                <div className="xg-display">
                  <div className="xg-team">
                    <div className="xg-team__name">{homeTeam}</div>
                    <div className="xg-team__value">{prediction.home_xg.toFixed(2)}</div>
                  </div>
                  <div className="xg-separator">-</div>
                  <div className="xg-team">
                    <div className="xg-team__value">{prediction.away_xg.toFixed(2)}</div>
                    <div className="xg-team__name">{awayTeam}</div>
                  </div>
                </div>
              </div>

              {/* BTTS */}
              {bttsMarket && (
                <div className="prediction-card">
                  <h3 className="prediction-card__title">Karşılıklı Gol (BTTS)</h3>
                  <div className="prediction-grid prediction-grid--two">
                    {bttsMarket.outcomes.map((outcome) => (
                      <div key={outcome.label} className="prediction-outcome">
                        <div className="prediction-outcome__label">
                          {outcome.label === 'Yes' ? 'Evet' : 'Hayır'}
                        </div>
                        <ProbabilityDisplay probability={outcome.model_probability} />
                        <div className="prediction-outcome__odds">
                          Adil Oran: {outcome.fair_odds.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Over/Under */}
              <div className="prediction-card">
                <h3 className="prediction-card__title">Toplam Gol</h3>
                <div className="ou-markets">
                  {over25Market && (
                    <div className="ou-market">
                      <div className="ou-market__title">Üst/Alt 2.5</div>
                      <div className="prediction-grid prediction-grid--two">
                        {over25Market.outcomes.map((outcome) => (
                          <div key={outcome.label} className="prediction-outcome">
                            <div className="prediction-outcome__label">{outcome.label}</div>
                            <ProbabilityDisplay probability={outcome.model_probability} />
                            <div className="prediction-outcome__odds">
                              Adil Oran: {outcome.fair_odds.toFixed(2)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {over35Market && (
                    <div className="ou-market">
                      <div className="ou-market__title">Üst/Alt 3.5</div>
                      <div className="prediction-grid prediction-grid--two">
                        {over35Market.outcomes.map((outcome) => (
                          <div key={outcome.label} className="prediction-outcome">
                            <div className="prediction-outcome__label">{outcome.label}</div>
                            <ProbabilityDisplay probability={outcome.model_probability} />
                            <div className="prediction-outcome__odds">
                              Adil Oran: {outcome.fair_odds.toFixed(2)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {!over25Market && !over35Market && (
                  <div className="unavailable-data">
                    Toplam gol tahminleri mevcut değil
                  </div>
                )}
              </div>

              {/* Easy Match Info */}
              {prediction.easy_match && prediction.easy_match.is_easy_match && (
                <div className="prediction-card prediction-card--highlight">
                  <h3 className="prediction-card__title">
                    ✅ Kolay Maç Tespit Edildi
                  </h3>
                  <div className="easy-match-info">
                    <div className="easy-match-score">
                      <div className="easy-match-score__label">Güven Skoru</div>
                      <div className="easy-match-score__value">
                        <ConfidenceIndicator 
                          confidence={prediction.easy_match.confidence_score} 
                        />
                      </div>
                    </div>

                    {prediction.easy_match.dominant_outcome && (
                      <div className="easy-match-dominant">
                        <div className="easy-match-dominant__label">Öne Çıkan Sonuç</div>
                        <div className="easy-match-dominant__outcome">
                          {prediction.easy_match.dominant_outcome}
                        </div>
                        <div className="easy-match-dominant__probability">
                          <ProbabilityDisplay 
                            probability={prediction.easy_match.dominant_probability || 0} 
                          />
                        </div>
                      </div>
                    )}

                    {prediction.easy_match.reasons.length > 0 && (
                      <div className="easy-match-reasons">
                        <div className="easy-match-reasons__label">Nedenler</div>
                        <ul className="easy-match-reasons__list">
                          {prediction.easy_match.reasons.map((reason, idx) => (
                            <li key={idx}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Bookmaker Comparison - Only if available */}
              {matchResultMarket?.bookmaker_comparison && (
                <div className="prediction-card">
                  <h3 className="prediction-card__title">Bahis Değer Analizi</h3>
                  <div className="bookmaker-comparison">
                    {matchResultMarket.bookmaker_comparison.map((comparison) => (
                      <div key={comparison.label} className="bookmaker-item">
                        <div className="bookmaker-item__label">{comparison.label}</div>
                        <div className="bookmaker-item__odds">
                          Bahisçi Oranı: {comparison.bookmaker_odds.toFixed(2)}
                        </div>
                        <div className="bookmaker-item__value">
                          <ValueIndicator value={comparison.edge_value} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Finished Match - Show Results Only */}
      {match.status === 'finished' && (
        <div className="match-result-section">
          <h2 className="section-title">Maç Sonucu</h2>
          <div className="final-score">
            <span className="final-score__label">Sonuç:</span>
            <span className="final-score__value">
              {match.home_score} - {match.away_score}
            </span>
          </div>
          {match.outcome && (
            <div className="match-outcome">
              <span className="match-outcome__label">Kazanan:</span>
              <span className="match-outcome__value">
                {match.outcome === 'home_win' ? homeTeam : 
                 match.outcome === 'away_win' ? awayTeam : 
                 'Beraberlik'}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
