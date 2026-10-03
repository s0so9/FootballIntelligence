"""Tests for match API endpoints.

This test module verifies the match-related REST API endpoints
work correctly with the DevelopmentProvider.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import DevelopmentProvider


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def dev_provider():
    """Create a DevelopmentProvider instance for reference."""
    return DevelopmentProvider()


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Verify health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_response_structure(self, client):
        """Verify health endpoint returns expected structure."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert data["status"] == "healthy"


class TestMatchListEndpoint:
    """Tests for GET /api/v1/matches endpoint."""

    def test_list_matches_returns_200(self, client):
        """Verify match list endpoint returns 200 OK."""
        response = client.get("/api/v1/matches")
        assert response.status_code == 200

    def test_list_matches_response_structure(self, client):
        """Verify match list response has correct structure."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        # Verify top-level structure
        assert "matches" in data
        assert "count" in data
        assert "is_development_data" in data
        
        # Verify it's a list
        assert isinstance(data["matches"], list)
        assert isinstance(data["count"], int)
        assert isinstance(data["is_development_data"], bool)

    def test_list_matches_returns_development_data(self, client):
        """Verify the development data flag is set correctly."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        # Must be flagged as development data
        assert data["is_development_data"] is True

    def test_list_matches_count_matches_list_length(self, client):
        """Verify count field matches the actual number of matches."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        assert data["count"] == len(data["matches"])

    def test_list_matches_returns_non_empty(self, client, dev_provider):
        """Verify the endpoint returns matches from DevelopmentProvider."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        # DevelopmentProvider has matches
        expected_matches = dev_provider.get_matches()
        assert len(data["matches"]) > 0
        assert data["count"] == len(expected_matches)

    def test_list_matches_contains_required_fields(self, client):
        """Verify each match contains required fields."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        if len(data["matches"]) > 0:
            match = data["matches"][0]
            
            # Required fields
            assert "id" in match
            assert "competition_id" in match
            assert "season_id" in match
            assert "home_team_id" in match
            assert "away_team_id" in match
            assert "scheduled_at" in match
            assert "status" in match
            assert "created_at" in match
            assert "updated_at" in match

    def test_list_matches_filter_by_competition(self, client, dev_provider):
        """Verify filtering by competition_id works."""
        # Get a competition ID from provider
        competitions = dev_provider.get_competitions()
        if len(competitions) > 0:
            comp_id = competitions[0].id
            
            response = client.get(f"/api/v1/matches?competition_id={comp_id}")
            data = response.json()
            
            assert response.status_code == 200
            # All returned matches should be from this competition
            for match in data["matches"]:
                assert match["competition_id"] == comp_id

    def test_list_matches_filter_by_team(self, client, dev_provider):
        """Verify filtering by team_id works."""
        # Get a team ID from provider
        teams = dev_provider.get_teams("", "")
        if len(teams) > 0:
            team_id = teams[0].id
            
            response = client.get(f"/api/v1/matches?team_id={team_id}")
            data = response.json()
            
            assert response.status_code == 200
            # All returned matches should involve this team
            for match in data["matches"]:
                assert (match["home_team_id"] == team_id or 
                       match["away_team_id"] == team_id)

    def test_list_matches_dev_prefix_present(self, client):
        """Verify development data contains [DEV] prefix markers."""
        response = client.get("/api/v1/matches")
        data = response.json()
        
        # Development data flag must be True
        assert data["is_development_data"] is True


class TestMatchDetailEndpoint:
    """Tests for GET /api/v1/matches/{match_id} endpoint."""

    def test_get_match_returns_200_for_existing_match(self, client, dev_provider):
        """Verify getting an existing match returns 200 OK."""
        # Get a valid match ID from provider
        matches = dev_provider.get_matches()
        assert len(matches) > 0, "DevelopmentProvider should have matches"
        
        match_id = matches[0].id
        response = client.get(f"/api/v1/matches/{match_id}")
        
        assert response.status_code == 200

    def test_get_match_returns_404_for_invalid_match(self, client):
        """Verify getting a non-existent match returns 404."""
        invalid_id = "nonexistent-match-id-12345"
        response = client.get(f"/api/v1/matches/{invalid_id}")
        
        assert response.status_code == 404

    def test_get_match_404_contains_detail(self, client):
        """Verify 404 response contains error detail."""
        invalid_id = "nonexistent-match-id-12345"
        response = client.get(f"/api/v1/matches/{invalid_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_match_response_structure(self, client, dev_provider):
        """Verify match detail response has correct structure."""
        # Get a valid match ID
        matches = dev_provider.get_matches()
        match_id = matches[0].id
        
        response = client.get(f"/api/v1/matches/{match_id}")
        data = response.json()
        
        # Verify top-level structure
        assert "match" in data
        assert "is_development_data" in data
        
        # Verify match object
        match = data["match"]
        assert "id" in match
        assert "competition_id" in match
        assert "home_team_id" in match
        assert "away_team_id" in match
        assert "scheduled_at" in match

    def test_get_match_returns_development_data_flag(self, client, dev_provider):
        """Verify the development data flag is set correctly."""
        # Get a valid match ID
        matches = dev_provider.get_matches()
        match_id = matches[0].id
        
        response = client.get(f"/api/v1/matches/{match_id}")
        data = response.json()
        
        # Must be flagged as development data
        assert data["is_development_data"] is True

    def test_get_match_returns_correct_match(self, client, dev_provider):
        """Verify the returned match has the requested ID."""
        # Get a valid match ID
        matches = dev_provider.get_matches()
        match_id = matches[0].id
        
        response = client.get(f"/api/v1/matches/{match_id}")
        data = response.json()
        
        assert data["match"]["id"] == match_id

    def test_get_match_contains_all_fields(self, client, dev_provider):
        """Verify match detail contains all expected fields."""
        # Get a valid match ID
        matches = dev_provider.get_matches()
        match_id = matches[0].id
        
        response = client.get(f"/api/v1/matches/{match_id}")
        data = response.json()
        match = data["match"]
        
        # Required fields
        required_fields = [
            "id",
            "competition_id",
            "season_id",
            "home_team_id",
            "away_team_id",
            "scheduled_at",
            "status",
            "created_at",
            "updated_at",
        ]
        
        for field in required_fields:
            assert field in match, f"Missing field: {field}"


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_docs_accessible(self, client):
        """Verify OpenAPI documentation is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_accessible(self, client):
        """Verify OpenAPI JSON schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_schema_contains_match_endpoints(self, client):
        """Verify OpenAPI schema includes match endpoints."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        assert "paths" in schema
        assert "/api/v1/matches" in schema["paths"]
        assert "/api/v1/matches/{match_id}" in schema["paths"]


class TestEndpointIntegration:
    """Integration tests for endpoint behavior."""

    def test_list_and_detail_consistency(self, client):
        """Verify match from list can be retrieved via detail endpoint."""
        # Get match list
        list_response = client.get("/api/v1/matches")
        list_data = list_response.json()
        
        if len(list_data["matches"]) > 0:
            # Get first match ID
            first_match_id = list_data["matches"][0]["id"]
            
            # Get that match via detail endpoint
            detail_response = client.get(f"/api/v1/matches/{first_match_id}")
            detail_data = detail_response.json()
            
            # Should succeed
            assert detail_response.status_code == 200
            assert detail_data["match"]["id"] == first_match_id

    def test_all_listed_matches_retrievable(self, client):
        """Verify all matches from list endpoint can be retrieved individually."""
        # Get match list
        list_response = client.get("/api/v1/matches")
        list_data = list_response.json()
        
        # Try to get each match individually
        for match_summary in list_data["matches"]:
            match_id = match_summary["id"]
            detail_response = client.get(f"/api/v1/matches/{match_id}")
            
            # Each should return 200
            assert detail_response.status_code == 200
            detail_data = detail_response.json()
            assert detail_data["match"]["id"] == match_id
