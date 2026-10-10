/**
 * Popular Competition Identification
 * 
 * Identifies major football competitions that should receive
 * prioritized prediction loading.
 */

/**
 * Popular competitions that should receive prioritized predictions.
 * Based on competition/league names commonly used in football data.
 */
const POPULAR_COMPETITION_KEYWORDS = [
  // English
  'premier league',
  'championship',
  'efl',
  
  // Spanish
  'la liga',
  'laliga',
  
  // German
  'bundesliga',
  
  // Italian
  'serie a',
  
  // French
  'ligue 1',
  
  // Turkish
  'süper lig',
  'super lig',
  'superlig',
  
  // Brazilian
  'brasileirão',
  'brasileirao',
  'brasileiro',
  'brazil serie a',
  'serie a brazil',
  'campeonato brasileiro',
  
  // European
  'champions league',
  'uefa champions',
  'europa league',
  'uefa europa',
  'conference league',
  
  // Other major leagues
  'eredivisie',
  'primeira liga',
  'scottish premiership',
];

/**
 * Check if a competition is considered popular based on its name.
 */
export function isPopularCompetition(competitionName: string | undefined): boolean {
  if (!competitionName) return false;
  
  const normalized = competitionName.toLowerCase().trim();
  
  return POPULAR_COMPETITION_KEYWORDS.some(keyword => 
    normalized.includes(keyword)
  );
}

/**
 * Check if a competition is popular based on competition_id pattern.
 * Many data sources use specific ID patterns for major competitions.
 */
export function isPopularCompetitionById(competitionId: string | undefined): boolean {
  if (!competitionId) return false;
  
  // Common ID patterns for major competitions in various data sources
  // This is a heuristic - actual IDs depend on the data provider
  const popularIdPatterns = [
    /^(PL|EPL)/i,        // Premier League
    /^(LL|LAL)/i,        // La Liga
    /^(BL|BUN)/i,        // Bundesliga
    /^(SA|SER)/i,        // Serie A
    /^(L1|LIG)/i,        // Ligue 1
    /^(SL|SUP)/i,        // Süper Lig
    /^(CL|UCL)/i,        // Champions League
    /^(EL|UEL)/i,        // Europa League
  ];
  
  return popularIdPatterns.some(pattern => pattern.test(competitionId));
}

/**
 * Filter matches to only those from popular competitions.
 */
export function filterPopularMatches<T extends { competition_id?: string }>(
  matches: T[],
  getCompetitionName?: (match: T) => string | undefined
): T[] {
  return matches.filter(match => {
    // Check by ID first (fast)
    if (isPopularCompetitionById(match.competition_id)) {
      return true;
    }
    
    // Check by name if getter provided (slower)
    if (getCompetitionName) {
      const name = getCompetitionName(match);
      if (isPopularCompetition(name)) {
        return true;
      }
    }
    
    return false;
  });
}

/**
 * Normalize competition name for display.
 * Handles provider-specific variations and returns a canonical display name.
 * 
 * This function does NOT hardcode IDs or create fake competitions.
 * It only normalizes known competition name patterns for better UI display.
 */
export function normalizeCompetitionName(competitionName: string | undefined): string | undefined {
  if (!competitionName) return undefined;
  
  const normalized = competitionName.toLowerCase().trim();
  
  // Brazilian Serie A variations
  if (
    normalized.includes('brasileirão') ||
    normalized.includes('brasileirao') ||
    normalized.includes('brasileiro') ||
    (normalized.includes('brazil') && normalized.includes('serie a')) ||
    (normalized.includes('serie a') && normalized.includes('brazil')) ||
    normalized.includes('campeonato brasileiro')
  ) {
    return 'Brasileirão Série A';
  }
  
  // Return original if no normalization pattern matches
  return competitionName;
}
