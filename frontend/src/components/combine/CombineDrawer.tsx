/**
 * CombineDrawer Component
 * 
 * Displays combine selections with total odds calculation and potential return.
 * AI confidence NEVER enters odds calculations.
 * Bottom drawer on mobile, side panel on desktop.
 */

import { useState } from 'react'
import type { CombineItem } from '../../hooks/useCombine'
import './CombineDrawer.css'

interface CombineDrawerProps {
  /** Combine items */
  items: CombineItem[]
  /** Callback to remove item */
  onRemove: (matchId: string) => void
  /** Callback to clear all items */
  onClear: () => void
}

export default function CombineDrawer({
  items,
  onRemove,
  onClear
}: CombineDrawerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [stake, setStake] = useState(10)

  // Calculate total odds (product of all odds)
  const totalOdds = items.reduce((product, item) => product * item.odds, 1)
  
  // Calculate potential return (totalOdds × stake)
  const potentialReturn = totalOdds * stake

  // Check if any item has no odds
  const hasInvalidOdds = items.some(item => !item.odds || item.odds <= 0)

  return (
    <>
      {/* Toggle button */}
      <button
        type="button"
        className="combine-drawer-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={isOpen ? 'Kombineyi kapat' : 'Kombineyi aç'}
        aria-expanded={isOpen}
      >
        <span className="combine-drawer-toggle__icon">🎯</span>
        <span className="combine-drawer-toggle__text">Kombine</span>
        {items.length > 0 && (
          <span className="combine-drawer-toggle__badge">{items.length}</span>
        )}
      </button>

      {/* Drawer */}
      <aside
        className={`combine-drawer ${isOpen ? 'combine-drawer--open' : ''}`}
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="combine-drawer__header">
          <h3 className="combine-drawer__title">
            Kombine ({items.length})
          </h3>
          <button
            type="button"
            className="combine-drawer__close-button"
            onClick={() => setIsOpen(false)}
            aria-label="Kapat"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="combine-drawer__content">
          {items.length === 0 ? (
            <div className="combine-drawer__empty-state">
              <div className="empty-state-icon">🎯</div>
              <p className="empty-state-text">Henüz seçim eklenmedi</p>
            </div>
          ) : (
            <>
              {/* Items list */}
              <div className="combine-items">
                {items.map((item) => (
                  <div key={item.matchId} className="combine-item">
                    <div className="combine-item__match">
                      {item.homeTeam} vs {item.awayTeam}
                    </div>
                    <div className="combine-item__market">
                      {item.marketName}
                      {item.outcome && ` - ${item.outcome}`}
                    </div>
                    <div className="combine-item__odds">
                      Oran: {item.odds > 0 ? item.odds.toFixed(2) : 'Yok'}
                    </div>
                    <button
                      type="button"
                      className="combine-item__remove-button"
                      onClick={() => onRemove(item.matchId)}
                      aria-label="Kaldır"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              {/* Summary */}
              <div className="combine-summary">
                {/* Stake input */}
                <div className="combine-summary__stake">
                  <label htmlFor="stake-input" className="stake-label">
                    Bahis Miktarı (₺)
                  </label>
                  <input
                    id="stake-input"
                    type="number"
                    className="stake-input"
                    value={stake}
                    onChange={(e) => setStake(Math.max(0, parseFloat(e.target.value) || 0))}
                    min="0"
                    step="10"
                  />
                </div>

                {/* Total odds */}
                <div className="combine-summary__row">
                  <span className="combine-summary__label">Toplam Oran</span>
                  <span className="combine-summary__value">
                    {hasInvalidOdds ? 'Oran Yok' : totalOdds.toFixed(2)}
                  </span>
                </div>

                {/* Potential return */}
                <div className="combine-summary__row combine-summary__row--highlight">
                  <span className="combine-summary__label">Potansiyel Kazanç</span>
                  <span className="combine-summary__value">
                    {hasInvalidOdds ? '---' : `₺${potentialReturn.toFixed(2)}`}
                  </span>
                </div>

                {/* Warning if invalid odds */}
                {hasInvalidOdds && (
                  <div className="combine-summary__warning">
                    ⚠️ Bazı seçimlerin oranı mevcut değil
                  </div>
                )}

                {/* Clear button */}
                <button
                  type="button"
                  className="clear-button"
                  onClick={onClear}
                >
                  Tümünü Temizle
                </button>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Backdrop (mobile) */}
      {isOpen && (
        <div
          className="combine-drawer-backdrop"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}
    </>
  )
}
