"""
State machine configuration: presets, policies, and thresholds.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SensitivityPreset(Enum):
    """
    Sensitivity presets for posture detection.
    
    SENSITIVE (default v1): Lower thresholds, shorter windows, more responsive
    STANDARD: Moderate thresholds and windows
    CONSERVATIVE: Higher thresholds, longer windows, fewer false positives
    """
    SENSITIVE = "sensitive"
    STANDARD = "standard"
    CONSERVATIVE = "conservative"


@dataclass
class SustainPolicy:
    """
    Policy for sustained condition detection.
    
    Uses majority/cumulative logic with grace gaps:
    - Majority: >=majority_fraction of samples above threshold in window
    - Cumulative: Total time above threshold >= cumulative_min_sec
    - Grace gaps: Allow brief dips <= gap_budget_sec without resetting
    - High severity: Immediate trigger if very bad posture sustained
    """
    window_sec: float                    # Trailing window duration
    majority_fraction: float             # Required fraction above threshold (0.6 = 60%)
    gap_budget_sec: float                # Max allowed gap below threshold
    cumulative_min_sec: float            # Alternative: total time above threshold
    high_severity_delta_deg: float       # Delta for immediate trigger
    high_severity_window_sec: float      # Duration for high severity trigger
    
    def __post_init__(self):
        """Validate policy parameters."""
        assert 0.5 <= self.majority_fraction <= 1.0, "majority_fraction must be 0.5-1.0"
        assert self.gap_budget_sec < self.window_sec, "gap_budget must be < window"
        assert self.cumulative_min_sec <= self.window_sec, "cumulative_min must be <= window"


@dataclass
class StateConfig:
    """
    Configuration for state machine thresholds and windows.
    
    Sensitivity Presets:
    - SENSITIVE (default v1): neck +8°, torso +8°, lateral ~3cm; 
      window 30s (neck/torso), 40s (lateral); majority 0.60; gap 3s
    - STANDARD: neck +10°, torso +10°; majority 0.65; window +5s each
    - CONSERVATIVE: neck +12°, torso +12°; majority 0.70; window +10s each; gap 2s
    """
    # Thresholds (degrees or cm above baseline)
    slouch_threshold_deg: float = 8.0      # neck flexion (was 15.0)
    forward_lean_threshold_deg: float = 8.0  # torso flexion (was 12.0)
    lateral_lean_threshold_cm: float = 3.0   # shoulder asymmetry in cm (scale-adjusted)
    
    # Sustain policies per metric
    slouch_policy: Optional[SustainPolicy] = None
    forward_lean_policy: Optional[SustainPolicy] = None
    lateral_lean_policy: Optional[SustainPolicy] = None
    
    # Recovery window (seconds to stay below threshold before returning to GOOD)
    recovery_window_sec: float = 12.0
    recovery_majority_fraction: float = 0.60
    
    # Baseline drift correction (very slow EMA when in GOOD)
    # DISABLED for M1 - was causing runaway threshold increases
    drift_alpha: float = 0.0  # Was: 0.005
    
    # Confidence threshold for PAUSED state
    confidence_threshold: float = 0.5
    
    # Active preset (for telemetry)
    preset: SensitivityPreset = SensitivityPreset.SENSITIVE
    
    def __post_init__(self):
        """Initialize sustain policies if not provided."""
        if self.slouch_policy is None:
            self.slouch_policy = self._get_default_slouch_policy()
        if self.forward_lean_policy is None:
            self.forward_lean_policy = self._get_default_forward_policy()
        if self.lateral_lean_policy is None:
            self.lateral_lean_policy = self._get_default_lateral_policy()
    
    def _get_default_slouch_policy(self) -> SustainPolicy:
        """Get default slouch policy based on preset."""
        if self.preset == SensitivityPreset.SENSITIVE:
            return SustainPolicy(
                window_sec=30.0,
                majority_fraction=0.60,
                gap_budget_sec=3.0,
                cumulative_min_sec=18.0,
                high_severity_delta_deg=20.0,
                high_severity_window_sec=8.0
            )
        elif self.preset == SensitivityPreset.STANDARD:
            return SustainPolicy(
                window_sec=35.0,
                majority_fraction=0.65,
                gap_budget_sec=3.0,
                cumulative_min_sec=23.0,
                high_severity_delta_deg=22.0,
                high_severity_window_sec=10.0
            )
        else:  # CONSERVATIVE
            return SustainPolicy(
                window_sec=40.0,
                majority_fraction=0.70,
                gap_budget_sec=2.0,
                cumulative_min_sec=28.0,
                high_severity_delta_deg=25.0,
                high_severity_window_sec=12.0
            )
    
    def _get_default_forward_policy(self) -> SustainPolicy:
        """Get default forward lean policy based on preset."""
        if self.preset == SensitivityPreset.SENSITIVE:
            return SustainPolicy(
                window_sec=30.0,
                majority_fraction=0.60,
                gap_budget_sec=3.0,
                cumulative_min_sec=18.0,
                high_severity_delta_deg=18.0,
                high_severity_window_sec=8.0
            )
        elif self.preset == SensitivityPreset.STANDARD:
            return SustainPolicy(
                window_sec=35.0,
                majority_fraction=0.65,
                gap_budget_sec=3.0,
                cumulative_min_sec=23.0,
                high_severity_delta_deg=20.0,
                high_severity_window_sec=10.0
            )
        else:  # CONSERVATIVE
            return SustainPolicy(
                window_sec=40.0,
                majority_fraction=0.70,
                gap_budget_sec=2.0,
                cumulative_min_sec=28.0,
                high_severity_delta_deg=22.0,
                high_severity_window_sec=12.0
            )
    
    def _get_default_lateral_policy(self) -> SustainPolicy:
        """Get default lateral lean policy based on preset."""
        if self.preset == SensitivityPreset.SENSITIVE:
            return SustainPolicy(
                window_sec=40.0,
                majority_fraction=0.60,
                gap_budget_sec=3.0,
                cumulative_min_sec=24.0,
                high_severity_delta_deg=6.0,  # cm for lateral
                high_severity_window_sec=10.0
            )
        elif self.preset == SensitivityPreset.STANDARD:
            return SustainPolicy(
                window_sec=45.0,
                majority_fraction=0.65,
                gap_budget_sec=3.0,
                cumulative_min_sec=29.0,
                high_severity_delta_deg=7.0,
                high_severity_window_sec=12.0
            )
        else:  # CONSERVATIVE
            return SustainPolicy(
                window_sec=50.0,
                majority_fraction=0.70,
                gap_budget_sec=2.0,
                cumulative_min_sec=35.0,
                high_severity_delta_deg=8.0,
                high_severity_window_sec=15.0
            )
    
    @staticmethod
    def from_preset(preset: SensitivityPreset, **overrides) -> 'StateConfig':
        """
        Create config from preset with optional overrides.
        
        Args:
            preset: Sensitivity preset to use
            **overrides: Override specific config values
            
        Returns:
            StateConfig instance
        """
        if preset == SensitivityPreset.SENSITIVE:
            config = StateConfig(
                slouch_threshold_deg=8.0,
                forward_lean_threshold_deg=8.0,
                lateral_lean_threshold_cm=3.0,
                preset=preset
            )
        elif preset == SensitivityPreset.STANDARD:
            config = StateConfig(
                slouch_threshold_deg=10.0,
                forward_lean_threshold_deg=10.0,
                lateral_lean_threshold_cm=3.5,
                preset=preset
            )
        else:  # CONSERVATIVE
            config = StateConfig(
                slouch_threshold_deg=12.0,
                forward_lean_threshold_deg=12.0,
                lateral_lean_threshold_cm=4.0,
                preset=preset
            )
        
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
