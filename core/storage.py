"""
Local storage for calibration baselines and settings.
Uses JSON for simplicity in M1 (SQLite in M2 if needed).

PRIVACY: Only stores metrics (angles, timestamps), never frames.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CalibrationBaseline:
    """Calibration baseline data."""
    neck_flexion_baseline: float  # degrees
    torso_flexion_baseline: float  # degrees
    lateral_lean_baseline: float  # normalized ratio
    shoulder_width_proxy: float  # normalized scale factor
    calibrated_at: str  # ISO timestamp
    sample_count: int  # number of samples used
    confidence_mean: float  # average confidence during calibration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalibrationBaseline':
        """Create from dictionary."""
        return cls(**data)


class CalibrationStorage:
    """
    Manages local storage of calibration baselines.
    
    Storage location: ./storage/calibration.json
    Privacy: Only metrics stored, never frames.
    """
    
    def __init__(self, storage_dir: str = "./storage"):
        """
        Initialize calibration storage.
        
        Args:
            storage_dir: Directory for storage files
        """
        self.storage_dir = Path(storage_dir)
        self.calibration_file = self.storage_dir / "calibration.json"
        
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_baseline(self, baseline: CalibrationBaseline) -> bool:
        """
        Save calibration baseline to disk.
        
        Args:
            baseline: Calibration baseline data
            
        Returns:
            True if saved successfully
        """
        try:
            data = {
                "version": "1.0",
                "baseline": baseline.to_dict()
            }
            
            with open(self.calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to save baseline: {e}")
            return False
    
    def load_baseline(self) -> Optional[CalibrationBaseline]:
        """
        Load calibration baseline from disk.
        
        Returns:
            CalibrationBaseline if exists, None otherwise
        """
        if not self.calibration_file.exists():
            return None
        
        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
            
            # Version check (future-proofing)
            if data.get("version") != "1.0":
                print(f"WARNING: Unknown calibration file version: {data.get('version')}")
            
            baseline_data = data.get("baseline")
            if not baseline_data:
                return None
            
            return CalibrationBaseline.from_dict(baseline_data)
            
        except Exception as e:
            print(f"ERROR: Failed to load baseline: {e}")
            return None
    
    def delete_baseline(self) -> bool:
        """
        Delete calibration baseline (part of purge data).
        
        Returns:
            True if deleted successfully
        """
        try:
            if self.calibration_file.exists():
                self.calibration_file.unlink()
            return True
        except Exception as e:
            print(f"ERROR: Failed to delete baseline: {e}")
            return False
    
    def is_calibrated(self) -> bool:
        """Check if calibration baseline exists."""
        return self.calibration_file.exists()
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """
        Get calibration status summary.
        
        Returns:
            Dictionary with calibration status
        """
        baseline = self.load_baseline()
        
        if baseline is None:
            return {
                "calibrated": False,
                "message": "Not calibrated. Run calibration to establish baseline."
            }
        
        return {
            "calibrated": True,
            "calibrated_at": baseline.calibrated_at,
            "neck_baseline": baseline.neck_flexion_baseline,
            "torso_baseline": baseline.torso_flexion_baseline,
            "lateral_baseline": baseline.lateral_lean_baseline,
            "shoulder_width": baseline.shoulder_width_proxy,
            "sample_count": baseline.sample_count,
            "confidence_mean": baseline.confidence_mean
        }
