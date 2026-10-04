/**
 * Data Formatting Utilities
 */

import type { MatchStatus } from '../api/types';

/**
 * Format team ID to display name.
 * Converts "dev_team_alpha" to "Alpha".
 * Returns original if pattern doesn't match.
 */
export function formatTeamName(teamId: string): string {
  // Handle [DEV] prefixed names
  if (teamId.startsWith('[DEV]')) {
    return teamId.replace('[DEV]', '').trim();
  }

  // Handle dev_team_name pattern
  const match = teamId.match(/^dev_team_(.+)$/);
  if (match) {
    const name = match[1];
    // Capitalize first letter
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  // Return as-is if no pattern matches
  return teamId;
}

/**
 * Format competition ID to display name.
 */
export function formatCompetitionName(competitionId: string): string {
  if (competitionId.startsWith('[DEV]')) {
    return competitionId.replace('[DEV]', '').trim();
  }

  const match = competitionId.match(/^dev_comp_(.+)$/);
  if (match) {
    const name = match[1].replace(/_/g, ' ');
    return name
      .split(' ')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  return competitionId;
}

/**
 * Format match status to Turkish display text.
 */
export function formatMatchStatus(status: MatchStatus): string {
  const statusMap: Record<MatchStatus, string> = {
    scheduled: 'Planlandı',
    live: 'Canlı',
    finished: 'Bitti',
    postponed: 'Ertelendi',
    cancelled: 'İptal',
    abandoned: 'Yarıda Bırakıldı',
  };

  return statusMap[status] || status;
}

/**
 * Format date and time for match display.
 */
export function formatMatchDateTime(dateString: string): {
  date: string;
  time: string;
  full: string;
} {
  const date = new Date(dateString);

  const dateFormatted = date.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  const timeFormatted = date.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const fullFormatted = date.toLocaleString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return {
    date: dateFormatted,
    time: timeFormatted,
    full: fullFormatted,
  };
}

/**
 * Format match score display.
 */
export function formatScore(
  homeScore: number | null,
  awayScore: number | null
): string {
  if (homeScore === null || awayScore === null) {
    return '-';
  }
  return `${homeScore} - ${awayScore}`;
}
