/**
 * LeagueSelector Component
 * 
 * League/competition selector for Matches page.
 * Follows TUTAR X visual language.
 */

import type { CompetitionResponse } from '../api/types';
import './LeagueSelector.css';

interface LeagueSelectorProps {
  competitions: CompetitionResponse[];
  selectedId: string | null;
  onChange: (id: string) => void;
  loading: boolean;
}

export function LeagueSelector({ competitions, selectedId, onChange, loading }: LeagueSelectorProps) {
  if (loading) {
    return (
      <div className="league-selector">
        <div className="league-selector__loading">
          <div className="loading-spinner"></div>
          <p>Ligler yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (competitions.length === 0) {
    return (
      <div className="league-selector">
        <p className="league-selector__empty">Lig bulunamadı</p>
      </div>
    );
  }

  return (
    <div className="league-selector">
      <label className="league-selector__label">Lig Seç</label>
      <div className="league-selector__grid">
        {competitions.map((comp) => (
          <button
            key={comp.id}
            onClick={() => onChange(comp.id)}
            className={`league-btn ${selectedId === comp.id ? 'league-btn--active' : ''}`}
          >
            <span className="league-btn__name">{comp.name}</span>
            {comp.country && (
              <span className="league-btn__country">{comp.country}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
