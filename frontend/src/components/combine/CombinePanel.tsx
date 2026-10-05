/**
 * CombinePanel Component - Premium Betting Intelligence Panel
 * 
 * Bottom-right fixed panel showing combined bet selections.
 * Uses ONLY real market odds - never confidence, fair odds, or fabricated values.
 * 
 * Calculation: totalOdds = selections.reduce((total, odd) => total * odd, 1)
 * Potential return = stake * totalOdds
 */

import { useState } from 'react';
import type { CombineItem } from '../../hooks/useCombine';
import './CombinePanel.css';

interface CombinePanelProps {
  /** Combined selections */
  combineItems: CombineItem[];
  /** Remove item callback */
  onRemoveItem: (matchId: string) => void;
  /** Clear all callback */
  onClearAll: () => void;
}

const STAKE_PRESETS = [100, 250, 500, 1000, 5000] as const;

/**
 * Calculate total combined odds from real market odds only
 */
function calculateTotalOdds(items: CombineItem[]): number | null {
  // Filter items that have valid market odds
  const validOdds = items
    .map(item => item.marketOdds)
    .filter((odds): odds is number => odds !== null && odds > 0);
  
  // If any item doesn't have valid odds, cannot calculate
  if (validOdds.length !== items.length) {
    return null;
  }
  
  // Multiply all odds together
  return validOdds.reduce((total, odds) => total * odds, 1);
}

/**
 * Format number with proper Turkish locale and avoid floating-point artifacts
 */
function formatNumber(value: number, decimals: number = 2): string {
  return value.toFixed(decimals).replace(/\./, ',');
}

/**
 * Format currency in Turkish Lira
 */
function formatCurrency(value: number): string {
  return `${formatNumber(value, 2)} TL`;
}

export default function CombinePanel({
  combineItems,
  onRemoveItem,
  onClearAll
}: CombinePanelProps) {
  const [selectedStake, setSelectedStake] = useState<number>(100);
  
  const totalOdds = calculateTotalOdds(combineItems);
  const potentialReturn = totalOdds !== null ? selectedStake * totalOdds : null;
  const hasInvalidOdds = combineItems.some(item => item.marketOdds === null);
  
  // If no items, don't show panel
  if (combineItems.length === 0) {
    return null;
  }
  
  return (
    <aside className="combine-panel" aria-label="Kombine bahis paneli">
      <div className="combine-panel__header">
        <h2 className="combine-panel__title">KOMBİNE</h2>
        <button
          type="button"
          className="combine-panel__clear"
          onClick={onClearAll}
          aria-label="Tümünü temizle"
        >
          Temizle
        </button>
      </div>
      
      {/* Selected Matches */}
      <div className="combine-panel__selections">
        {combineItems.map((item) => (
          <div key={item.matchId} className="combine-selection">
            <div className="combine-selection__info">
              <div className="combine-selection__teams">
                {item.homeTeam} vs {item.awayTeam}
              </div>
              <div className="combine-selection__pick">
                {item.marketName}: {item.outcome}
              </div>
              <div className="combine-selection__odds">
                {item.marketOdds !== null ? formatNumber(item.marketOdds) : (
                  <span className="combine-selection__odds--unavailable">
                    Oran mevcut değil
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              className="combine-selection__remove"
              onClick={() => onRemoveItem(item.matchId)}
              aria-label="Kaldır"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      
      {/* Odds Multiplier */}
      <div className="combine-panel__multiplier">
        <div className="combine-panel__multiplier-label">ORAN ÇARPANI</div>
        <div className="combine-panel__multiplier-value">
          {totalOdds !== null ? formatNumber(totalOdds) : '--'}
        </div>
        {hasInvalidOdds && (
          <div className="combine-panel__warning">
            Bazı seçimlerin oranı mevcut değil
          </div>
        )}
      </div>
      
      {/* Stake Selector */}
      <div className="combine-panel__stake">
        <div className="combine-panel__stake-label">BAHIS MİKTARI</div>
        <div className="combine-panel__stake-grid">
          {STAKE_PRESETS.map((stake) => (
            <button
              key={stake}
              type="button"
              className={`stake-btn ${selectedStake === stake ? 'stake-btn--active' : ''}`}
              onClick={() => setSelectedStake(stake)}
            >
              {stake} TL
            </button>
          ))}
        </div>
      </div>
      
      {/* Potential Return */}
      <div className="combine-panel__return">
        <div className="combine-panel__return-label">TAHMİNİ KAZANÇ</div>
        <div className="combine-panel__return-value">
          {potentialReturn !== null ? formatCurrency(potentialReturn) : (
            <span className="combine-panel__return-value--unavailable">--</span>
          )}
        </div>
      </div>
      
      {/* Match Count */}
      <div className="combine-panel__count">
        {combineItems.length} maç seçildi
      </div>
    </aside>
  );
}
