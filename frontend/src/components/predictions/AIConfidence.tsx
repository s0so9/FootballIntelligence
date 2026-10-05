/**
 * AIConfidence Component
 * 
 * MENSIONE AI Confidence indicator with 1-6 money-bag scale.
 * Uses custom CSS icons with MENSIONE green glow that scales by confidence level.
 * 
 * Confidence Mapping (0-1 or 0-100):
 * 1/6 (Çok Düşük):  0.00 - 0.16
 * 2/6 (Düşük):      0.17 - 0.33
 * 3/6 (Orta):       0.34 - 0.50
 * 4/6 (İyi):        0.51 - 0.67
 * 5/6 (Yüksek):     0.68 - 0.83
 * 6/6 (Çok Yüksek): 0.84 - 1.00
 */

import './AIConfidence.css'

interface AIConfidenceProps {
  /** Confidence value (0-1 or 0-100) */
  confidence: number
  /** Show percentage text */
  showPercentage?: boolean
  /** Show level text (e.g., "5/6") */
  showLevel?: boolean
  /** Show Turkish label (e.g., "Yüksek") */
  showLabel?: boolean
  /** Component size variant */
  size?: 'sm' | 'md' | 'lg'
}

interface ConfidenceLevel {
  level: number
  label: string
  glowClass: string
}

const CONFIDENCE_LABELS = [
  'Çok düşük',
  'Düşük',
  'Orta',
  'İyi',
  'Yüksek',
  'Çok yüksek'
]

/**
 * Map confidence value (0-1 or 0-100) to 1-6 level
 */
function getConfidenceLevel(confidence: number): ConfidenceLevel {
  // Normalize to 0-1 range if value is > 1 (assume 0-100)
  const normalized = confidence > 1 ? confidence / 100 : confidence
  
  // Map to 1-6 scale
  let level: number
  if (normalized <= 0.16) {
    level = 1
  } else if (normalized <= 0.33) {
    level = 2
  } else if (normalized <= 0.5) {
    level = 3
  } else if (normalized <= 0.67) {
    level = 4
  } else if (normalized <= 0.83) {
    level = 5
  } else {
    level = 6
  }
  
  return {
    level,
    label: CONFIDENCE_LABELS[level - 1],
    glowClass: `ai-confidence__icon--glow-${level}`
  }
}

export default function AIConfidence({
  confidence,
  showPercentage = true,
  showLevel = true,
  showLabel = true,
  size = 'md'
}: AIConfidenceProps) {
  const { level, label, glowClass } = getConfidenceLevel(confidence)
  
  // Normalize confidence for display
  const normalizedConfidence = confidence > 1 ? confidence : confidence * 100
  
  // Generate array of 6 icons (filled vs inactive)
  const icons = Array.from({ length: 6 }, (_, index) => ({
    active: index < level,
    key: `icon-${index}`
  }))
  
  const sizeClass = `ai-confidence--${size}`
  
  return (
    <div className={`ai-confidence ${sizeClass}`} role="status" aria-label={`Yapay zeka güveni: ${label}, ${normalizedConfidence.toFixed(0)}%`}>
      {/* Title */}
      <div className="ai-confidence__title">Yapay Zeka Güveni</div>
      
      {/* Money-bag icons */}
      <div className="ai-confidence__icons" aria-hidden="true">
        {icons.map(({ active, key }) => (
          <div
            key={key}
            className={`ai-confidence__icon ${
              active ? `ai-confidence__icon--active ${glowClass}` : 'ai-confidence__icon--inactive'
            }`}
          >
            {/* SVG money bag icon */}
            <svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L8 6H16L12 2Z"/>
              <path d="M7 7C6.44772 7 6 7.44772 6 8V18C6 19.6569 7.34315 21 9 21H15C16.6569 21 18 19.6569 18 18V8C18 7.44772 17.5523 7 17 7H7Z"/>
              <circle cx="12" cy="14" r="3" opacity="0.6"/>
            </svg>
          </div>
        ))}
      </div>
      
      {/* Level and label */}
      <div className="ai-confidence__info">
        {showLevel && (
          <span className="ai-confidence__level">{level}/6</span>
        )}
        {showLabel && (
          <span className="ai-confidence__label">{label}</span>
        )}
      </div>
      
      {/* Percentage */}
      {showPercentage && (
        <div className="ai-confidence__percentage">
          %{normalizedConfidence.toFixed(0)}
        </div>
      )}
    </div>
  )
}
