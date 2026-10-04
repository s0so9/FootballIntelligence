"""Prediction versioning and immutable history tracking.

Tracks prediction evolution through match lifecycle stages:
- 7d_before: 7 days before match
- 24h_before: 24 hours before match
- lineup_confirmed: After lineups announced
- kickoff: At kickoff time
- live: During match (if live predictions enabled)

Once written, a prediction version is NEVER modified (immutable).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class PredictionStage(str, Enum):
    """Match lifecycle stages for prediction versioning."""
    
    SEVEN_DAYS_BEFORE = "7d_before"
    TWENTY_FOUR_HOURS_BEFORE = "24h_before"
    LINEUP_CONFIRMED = "lineup_confirmed"
    KICKOFF = "kickoff"
    LIVE = "live"


@dataclass
class PredictionVersion:
    """Immutable prediction version snapshot.
    
    Once created, a version's data cannot be modified. Updates create new versions.
    """
    
    # Version identification
    version_id: str
    """Unique version identifier (UUID)"""
    
    match_id: str
    """Match identifier"""
    
    stage: PredictionStage
    """Prediction stage in match lifecycle"""
    
    created_at: datetime
    """When this version was created (UTC)"""
    
    # Prediction data (immutable snapshot)
    prediction_data: Dict[str, Any]
    """Complete prediction output as JSON-serializable dict
    
    Structure:
    {
        "home_win_prob": float,
        "draw_prob": float,
        "away_win_prob": float,
        "home_xg": float,
        "away_xg": float,
        "markets": {...},
        "mensione_pick": {...},
        "confidence": {...},
        "player_impact": {...} or null,
        "tactical_matchup": {...} or null,
        "model_predictions": [...],
        "ensemble_metadata": {...}
    }
    """
    
    # Model metadata
    model_versions: Dict[str, str] = field(default_factory=dict)
    """Model versions used in this prediction: {model_id: version}"""
    
    # Data quality snapshot
    data_quality_score: float = 0.0
    """Data quality score at time of prediction [0, 1]"""
    
    confidence_score: float = 0.0
    """Overall confidence score [0, 1]"""
    
    # Metadata
    notes: List[str] = field(default_factory=list)
    """Any notes or warnings about this version"""
    
    def __post_init__(self):
        """Validate version after initialization."""
        if not self.version_id:
            raise ValueError("version_id cannot be empty")
        
        if not self.match_id:
            raise ValueError("match_id cannot be empty")
        
        if not isinstance(self.stage, PredictionStage):
            # Try to convert string to enum
            if isinstance(self.stage, str):
                self.stage = PredictionStage(self.stage)
            else:
                raise ValueError(f"stage must be PredictionStage, got {type(self.stage)}")
        
        if not (0.0 <= self.data_quality_score <= 1.0):
            raise ValueError(f"data_quality_score must be in [0, 1], got {self.data_quality_score}")
        
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(f"confidence_score must be in [0, 1], got {self.confidence_score}")


class PredictionVersionManager:
    """Manages prediction versioning and immutable history.
    
    Features:
    - Immutable version storage (no updates after creation)
    - Stage-based versioning
    - Complete version history retrieval
    - Duplicate stage detection (optional overwrite)
    
    Versions are persisted through PredictionPersistenceService.
    """
    
    def __init__(self, persistence_service=None):
        """Initialize version manager.
        
        Args:
            persistence_service: Optional PredictionPersistenceService for database storage
        """
        self.persistence_service = persistence_service
        # In-memory storage for testing (fallback if no persistence)
        self._memory_store: Dict[str, List[PredictionVersion]] = {}
    
    def create_version(
        self,
        match_id: str,
        stage: PredictionStage,
        prediction_data: Dict[str, Any],
        model_versions: Optional[Dict[str, str]] = None,
        data_quality_score: float = 0.0,
        confidence_score: float = 0.0,
        notes: Optional[List[str]] = None,
        allow_stage_overwrite: bool = False
    ) -> PredictionVersion:
        """Create new prediction version.
        
        Args:
            match_id: Match identifier
            stage: Prediction stage
            prediction_data: Complete prediction output
            model_versions: Model versions used
            data_quality_score: Data quality score
            confidence_score: Confidence score
            notes: Optional notes
            allow_stage_overwrite: If True, allow multiple versions for same stage
        
        Returns:
            Created PredictionVersion
        
        Raises:
            ValueError: If stage already exists and allow_stage_overwrite=False
        """
        # Check for existing version at this stage
        if not allow_stage_overwrite:
            existing = self.get_version_by_stage(match_id, stage)
            if existing:
                raise ValueError(
                    f"Version already exists for match {match_id} at stage {stage.value}. "
                    f"Set allow_stage_overwrite=True to create duplicate."
                )
        
        # Create version
        version = PredictionVersion(
            version_id=str(uuid.uuid4()),
            match_id=match_id,
            stage=stage,
            created_at=datetime.utcnow(),
            prediction_data=prediction_data.copy(),  # Deep copy to ensure immutability
            model_versions=model_versions or {},
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            notes=notes or []
        )
        
        # Persist version
        if self.persistence_service:
            self.persistence_service.save_version(version)
        else:
            # Fallback to in-memory
            if match_id not in self._memory_store:
                self._memory_store[match_id] = []
            self._memory_store[match_id].append(version)
        
        return version
    
    def get_versions(self, match_id: str) -> List[PredictionVersion]:
        """Get all prediction versions for a match.
        
        Args:
            match_id: Match identifier
        
        Returns:
            List of PredictionVersion ordered by created_at (oldest first)
        """
        if self.persistence_service:
            versions = self.persistence_service.get_versions(match_id)
        else:
            versions = self._memory_store.get(match_id, [])
        
        # Sort by creation time
        versions.sort(key=lambda v: v.created_at)
        
        return versions
    
    def get_latest_version(self, match_id: str) -> Optional[PredictionVersion]:
        """Get most recent prediction version for a match.
        
        Args:
            match_id: Match identifier
        
        Returns:
            Latest PredictionVersion or None if no versions exist
        """
        versions = self.get_versions(match_id)
        return versions[-1] if versions else None
    
    def get_version_by_stage(
        self,
        match_id: str,
        stage: PredictionStage
    ) -> Optional[PredictionVersion]:
        """Get prediction version for specific stage.
        
        If multiple versions exist for the stage, returns the latest.
        
        Args:
            match_id: Match identifier
            stage: Prediction stage
        
        Returns:
            PredictionVersion for stage or None if not found
        """
        versions = self.get_versions(match_id)
        stage_versions = [v for v in versions if v.stage == stage]
        
        return stage_versions[-1] if stage_versions else None
    
    def get_version_evolution(self, match_id: str) -> List[Dict[str, Any]]:
        """Get simplified version evolution for match.
        
        Returns compact representation of how prediction evolved over time.
        
        Args:
            match_id: Match identifier
        
        Returns:
            List of dicts with stage, timestamp, key metrics
        """
        versions = self.get_versions(match_id)
        
        evolution = []
        for version in versions:
            pred_data = version.prediction_data
            
            evolution.append({
                "stage": version.stage.value,
                "created_at": version.created_at.isoformat(),
                "home_win_prob": pred_data.get("home_win_prob"),
                "draw_prob": pred_data.get("draw_prob"),
                "away_win_prob": pred_data.get("away_win_prob"),
                "mensione_pick": pred_data.get("mensione_pick", {}).get("pick_market") if pred_data.get("mensione_pick") else None,
                "confidence": version.confidence_score
            })
        
        return evolution
    
    def delete_version(self, version_id: str) -> bool:
        """Delete a specific version.
        
        WARNING: This violates immutability principle. Use only for:
        - Testing/development cleanup
        - GDPR/legal compliance
        - Correcting serious errors
        
        Args:
            version_id: Version identifier to delete
        
        Returns:
            True if deleted, False if not found
        """
        if self.persistence_service:
            return self.persistence_service.delete_version(version_id)
        else:
            # In-memory deletion
            for match_id, versions in self._memory_store.items():
                for i, version in enumerate(versions):
                    if version.version_id == version_id:
                        del self._memory_store[match_id][i]
                        return True
            return False
