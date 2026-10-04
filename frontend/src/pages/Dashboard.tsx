import { useState, useEffect } from 'react';
import ProbabilityDisplay from '../components/common/ProbabilityDisplay';
import ConfidenceIndicator from '../components/common/ConfidenceIndicator';
import ValueIndicator from '../components/common/ValueIndicator';
import './Dashboard.css';

interface DashboardStats {
  totalMatches: number;
  easyMatches: number;
  avgConfidence: number | null;
  avgAccuracy: number | null;
}

interface EasyMatch {
  matchId: string;
  homeTeam: string;
  awayTeam: string;
  kickoffTime: string;
  prediction: string;
  probability: number;
  confidence: number;
  edge: number;
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [easyMatches, setEasyMatches] = useState<EasyMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch upcoming matches to calculate stats
        const matchesResponse = await fetch('/api/v1/matches/upcoming?days=7');
        if (!matchesResponse.ok) {
          throw new Error('Maç verileri alınamadı');
        }
        const matchesData = await matchesResponse.json();

        // Calculate stats from available data
        const dashboardStats: DashboardStats = {
          totalMatches: matchesData.length || 0,
          easyMatches: 0,
          avgConfidence: null,
          avgAccuracy: null,
        };

        // Fetch easy matches
        const easyMatchesData: EasyMatch[] = [];
        for (const match of matchesData.slice(0, 10)) {
          try {
            const predResponse = await fetch(`/api/v1/matches/${match.match_id}/prediction`);
            if (predResponse.ok) {
              const predData = await predResponse.json();
              if (predData.easy_match?.is_easy) {
                easyMatchesData.push({
                  matchId: match.match_id,
                  homeTeam: match.home_team,
                  awayTeam: match.away_team,
                  kickoffTime: match.kickoff_time,
                  prediction: predData.easy_match.outcome,
                  probability: predData.easy_match.probability,
                  confidence: predData.easy_match.confidence,
                  edge: predData.easy_match.edge,
                });
              }
            }
          } catch {
            // Skip this match if prediction fails
          }
        }

        dashboardStats.easyMatches = easyMatchesData.length;
        setStats(dashboardStats);
        setEasyMatches(easyMatchesData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Bir hata oluştu');
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h1>Ana Sayfa</h1>
        </div>
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Veriler yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h1>Ana Sayfa</h1>
        </div>
        <div className="error-state">
          <p className="error-message">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Ana Sayfa</h1>
        <p className="dashboard-subtitle">Futbol İstihbarat Platformu</p>
      </div>

      {/* Overview Stats */}
      <section className="dashboard-section">
        <h2 className="section-title">Genel Bakış</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-content">
              <div className="stat-label">Toplam Maç</div>
              <div className="stat-value">{stats?.totalMatches || 0}</div>
              <div className="stat-description">Önümüzdeki 7 gün</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">✅</div>
            <div className="stat-content">
              <div className="stat-label">Kolay Maç</div>
              <div className="stat-value">{stats?.easyMatches || 0}</div>
              <div className="stat-description">Yüksek güven seviyesi</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">🎯</div>
            <div className="stat-content">
              <div className="stat-label">Ortalama Güven</div>
              <div className="stat-value">
                {stats && stats.avgConfidence !== null ? (
                  <ConfidenceIndicator confidence={stats.avgConfidence} showLabel={false} />
                ) : (
                  <span className="stat-unavailable">—</span>
                )}
              </div>
              <div className="stat-description">Tahmin güvenilirliği</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-content">
              <div className="stat-label">Model Performansı</div>
              <div className="stat-value">
                {stats && stats.avgAccuracy !== null ? (
                  `${(stats.avgAccuracy * 100).toFixed(1)}%`
                ) : (
                  <span className="stat-unavailable">—</span>
                )}
              </div>
              <div className="stat-description">Geçmiş doğruluk</div>
            </div>
          </div>
        </div>
      </section>

      {/* Easy Matches */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2 className="section-title">Kolay Maçlar</h2>
          <a href="/easy-matches" className="section-link">Tümünü Gör →</a>
        </div>

        {easyMatches.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <p className="empty-title">Kolay maç bulunamadı</p>
            <p className="empty-description">
              Şu anda yüksek güven seviyesine sahip tahmin bulunmamaktadır.
            </p>
          </div>
        ) : (
          <div className="easy-matches-list">
            {easyMatches.map((match) => (
              <div key={match.matchId} className="easy-match-card">
                <div className="match-teams">
                  <div className="team-name">{match.homeTeam}</div>
                  <div className="match-vs">vs</div>
                  <div className="team-name">{match.awayTeam}</div>
                </div>
                <div className="match-time">
                  {new Date(match.kickoffTime).toLocaleString('tr-TR', {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
                <div className="match-prediction">
                  <div className="prediction-label">Tahmin</div>
                  <div className="prediction-outcome">{match.prediction}</div>
                </div>
                <div className="match-metrics">
                  <ProbabilityDisplay probability={match.probability} />
                  <ConfidenceIndicator confidence={match.confidence} />
                  <ValueIndicator value={match.edge} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Performance */}
      <section className="dashboard-section">
        <h2 className="section-title">Son Performans</h2>
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <p className="empty-title">Henüz veri yok</p>
          <p className="empty-description">
            Geçmiş tahmin performans verileri henüz mevcut değil.
          </p>
        </div>
      </section>
    </div>
  );
}
