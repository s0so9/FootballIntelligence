/**
 * Tests for Matches page
 * 
 * Regression tests for league-first loading flow and duplicate request prevention.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Matches } from '../Matches';
import * as api from '../../api';

// Mock API module
vi.mock('../../api', () => ({
  getCompetitions: vi.fn(),
  getMatches: vi.fn(),
}));

const mockGetCompetitions = vi.mocked(api.getCompetitions);
const mockGetMatches = vi.mocked(api.getMatches);

describe('Matches page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderMatches() {
    return render(
      <BrowserRouter>
        <Matches />
      </BrowserRouter>
    );
  }

  it('should load competitions and render LeagueSelector', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [
        { id: '47', name: 'Premier League', country: 'ENG' },
        { id: '87', name: 'La Liga', country: 'ESP' },
      ],
      count: 2,
      is_development_data: false,
    });

    renderMatches();

    // Should show loading state first
    expect(screen.getByText('Ligler yükleniyor...')).toBeInTheDocument();

    // Wait for competitions to load
    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    expect(screen.getByText('La Liga')).toBeInTheDocument();
    expect(mockGetCompetitions).toHaveBeenCalledTimes(1);
  });

  it('should call getMatches with correct competition_id when league selected', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [
        { id: '47', name: 'Premier League', country: 'ENG' },
      ],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [
        {
          id: 'match_1',
          competition_id: '47',
          season_id: 'season_1',
          home_team_id: 'team_1',
          away_team_id: 'team_2',
          venue_id: null,
          home_team: { id: 'team_1', name: 'Arsenal', short_name: 'ARS', code: 'ARS', logo_url: null },
          away_team: { id: 'team_2', name: 'Chelsea', short_name: 'CHE', code: 'CHE', logo_url: null },
          scheduled_at: '2025-12-15T15:00:00Z',
          status: 'scheduled',
          home_score: null,
          away_score: null,
          home_score_ht: null,
          away_score_ht: null,
          home_statistics: null,
          away_statistics: null,
          home_statistics_ht: null,
          away_statistics_ht: null,
          minute: null,
          added_time: null,
          outcome: null,
          round: 15,
          created_at: null,
          updated_at: null,
        },
      ],
      count: 1,
      is_development_data: false,
    });

    const user = userEvent.setup();
    renderMatches();

    // Wait for competitions to load
    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    // Click on Premier League
    await user.click(screen.getByText('Premier League'));

    // Should call getMatches with competition_id
    await waitFor(() => {
      expect(mockGetMatches).toHaveBeenCalledWith(
        expect.objectContaining({
          competition_id: '47',
          status: 'scheduled',
        })
      );
    });

    // Should show match with team names
    await waitFor(() => {
      expect(screen.getByText('Arsenal')).toBeInTheDocument();
      expect(screen.getByText('Chelsea')).toBeInTheDocument();
    });
  });

  it('should display team names from home_team.name / away_team.name', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [
        {
          id: 'match_1',
          competition_id: '47',
          season_id: 'season_1',
          home_team_id: 'team_1',
          away_team_id: 'team_2',
          venue_id: null,
          home_team: { id: 'team_1', name: 'Manchester United', short_name: 'MUN', code: 'MUN', logo_url: null },
          away_team: { id: 'team_2', name: 'Liverpool', short_name: 'LIV', code: 'LIV', logo_url: null },
          scheduled_at: '2025-12-20T17:30:00Z',
          status: 'scheduled',
          home_score: null,
          away_score: null,
          home_score_ht: null,
          away_score_ht: null,
          home_statistics: null,
          away_statistics: null,
          home_statistics_ht: null,
          away_statistics_ht: null,
          minute: null,
          added_time: null,
          outcome: null,
          round: 16,
          created_at: null,
          updated_at: null,
        },
      ],
      count: 1,
      is_development_data: false,
    });

    const user = userEvent.setup();
    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(screen.getByText('Manchester United')).toBeInTheDocument();
      expect(screen.getByText('Liverpool')).toBeInTheDocument();
    });
  });

  it('should show "Bu ligde yaklaşan maç bulunamadı" when no matches found', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockResolvedValue({
      matches: [],
      count: 0,
      is_development_data: false,
    });

    const user = userEvent.setup();
    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(screen.getByText('Bu ligde yaklaşan maç bulunamadı')).toBeInTheDocument();
    });
  });

  it('should handle competition API error gracefully', async () => {
    mockGetCompetitions.mockRejectedValue(new Error('Ligler yüklenirken bir hata oluştu'));

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText(/Ligler yüklenirken bir hata oluştu/i)).toBeInTheDocument();
    });

    // Page should not crash
    expect(screen.getByText('Maçlar')).toBeInTheDocument();
  });

  it('should show error state but keep league selector visible on match API error', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    mockGetMatches.mockRejectedValue(new Error('Maçlar yüklenirken bir hata oluştu'));

    const user = userEvent.setup();
    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Premier League'));

    await waitFor(() => {
      expect(screen.getByText(/Maçlar yüklenirken bir hata oluştu/i)).toBeInTheDocument();
    });

    // League selector should still be visible
    expect(screen.getByText('Premier League')).toBeInTheDocument();
  });

  it('should call getCompetitions only once on mount (no duplicates)', async () => {
    mockGetCompetitions.mockResolvedValue({
      competitions: [{ id: '47', name: 'Premier League', country: 'ENG' }],
      count: 1,
      is_development_data: false,
    });

    renderMatches();

    await waitFor(() => {
      expect(screen.getByText('Premier League')).toBeInTheDocument();
    });

    // Wait a bit to ensure no duplicate calls
    await new Promise(resolve => setTimeout(resolve, 100));

    expect(mockGetCompetitions).toHaveBeenCalledTimes(1);
  });
});
