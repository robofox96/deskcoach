"""
Configuration manager for persisting UI settings.

Saves/loads StateConfig and NudgeConfig to/from JSON.
PRIVACY: No frames, only configuration values.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from core import StateConfig, NudgeConfig, SensitivityPreset


class ConfigManager:
    """
    Manages persistence of configuration settings.
    
    Saves to storage/ui_config.json
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file (default: storage/ui_config.json)
        """
        if config_path is None:
            config_path = "storage/ui_config.json"
        
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save_config(
        self,
        state_config: StateConfig,
        nudge_config: NudgeConfig,
        system_config: Dict[str, Any]
    ):
        """
        Save configuration to JSON.
        
        Args:
            state_config: State machine configuration
            nudge_config: Nudge policy configuration
            system_config: System settings (FPS, camera, etc.)
        """
        config = {
            "state_config": {
                "preset": state_config.preset.value,
                "slouch_threshold_deg": state_config.slouch_threshold_deg,
                "forward_lean_threshold_deg": state_config.forward_lean_threshold_deg,
                "lateral_lean_threshold_cm": state_config.lateral_lean_threshold_cm,
                "recovery_window_sec": state_config.recovery_window_sec,
                "recovery_majority_fraction": state_config.recovery_majority_fraction,
                "drift_alpha": state_config.drift_alpha,
                "confidence_threshold": state_config.confidence_threshold,
                # Policies
                "slouch_policy": {
                    "window_sec": state_config.slouch_policy.window_sec,
                    "majority_fraction": state_config.slouch_policy.majority_fraction,
                    "gap_budget_sec": state_config.slouch_policy.gap_budget_sec,
                    "cumulative_min_sec": state_config.slouch_policy.cumulative_min_sec,
                    "high_severity_delta_deg": state_config.slouch_policy.high_severity_delta_deg,
                    "high_severity_window_sec": state_config.slouch_policy.high_severity_window_sec
                },
                "forward_lean_policy": {
                    "window_sec": state_config.forward_lean_policy.window_sec,
                    "majority_fraction": state_config.forward_lean_policy.majority_fraction,
                    "gap_budget_sec": state_config.forward_lean_policy.gap_budget_sec,
                    "cumulative_min_sec": state_config.forward_lean_policy.cumulative_min_sec,
                    "high_severity_delta_deg": state_config.forward_lean_policy.high_severity_delta_deg,
                    "high_severity_window_sec": state_config.forward_lean_policy.high_severity_window_sec
                },
                "lateral_lean_policy": {
                    "window_sec": state_config.lateral_lean_policy.window_sec,
                    "majority_fraction": state_config.lateral_lean_policy.majority_fraction,
                    "gap_budget_sec": state_config.lateral_lean_policy.gap_budget_sec,
                    "cumulative_min_sec": state_config.lateral_lean_policy.cumulative_min_sec,
                    "high_severity_delta_deg": state_config.lateral_lean_policy.high_severity_delta_deg,
                    "high_severity_window_sec": state_config.lateral_lean_policy.high_severity_window_sec
                }
            },
            "nudge_config": {
                "cooldown_done_sec": nudge_config.cooldown_done_sec,
                "cooldown_snooze_sec": nudge_config.cooldown_snooze_sec,
                "dismiss_backoff_neck_deg": nudge_config.dismiss_backoff_neck_deg,
                "dismiss_backoff_torso_deg": nudge_config.dismiss_backoff_torso_deg,
                "dismiss_backoff_lateral_cm": nudge_config.dismiss_backoff_lateral_cm,
                "dismiss_backoff_duration_sec": nudge_config.dismiss_backoff_duration_sec,
                "dedupe_window_sec": nudge_config.dedupe_window_sec,
                "nudge_expiry_sec": nudge_config.nudge_expiry_sec,
                "respect_dnd": nudge_config.respect_dnd,
                "allow_stacking": nudge_config.allow_stacking,
                "high_severity_bypass_dedupe": nudge_config.high_severity_bypass_dedupe
            },
            "system_config": system_config
        }
        
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON.
        
        Returns:
            Dictionary with state_config, nudge_config, system_config
        """
        if not self.config_path.exists():
            return self._get_default_config()
        
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        state_config = StateConfig.from_preset(SensitivityPreset.SENSITIVE)
        nudge_config = NudgeConfig()
        
        return {
            "state_config": {
                "preset": "sensitive",
                "slouch_threshold_deg": 8.0,
                "forward_lean_threshold_deg": 8.0,
                "lateral_lean_threshold_cm": 3.0,
                "recovery_window_sec": 12.0,
                "recovery_majority_fraction": 0.60,
                "drift_alpha": 0.005,
                "confidence_threshold": 0.5,
                "slouch_policy": {
                    "window_sec": 30.0,
                    "majority_fraction": 0.60,
                    "gap_budget_sec": 3.0,
                    "cumulative_min_sec": 18.0,
                    "high_severity_delta_deg": 20.0,
                    "high_severity_window_sec": 8.0
                },
                "forward_lean_policy": {
                    "window_sec": 30.0,
                    "majority_fraction": 0.60,
                    "gap_budget_sec": 3.0,
                    "cumulative_min_sec": 18.0,
                    "high_severity_delta_deg": 18.0,
                    "high_severity_window_sec": 8.0
                },
                "lateral_lean_policy": {
                    "window_sec": 40.0,
                    "majority_fraction": 0.60,
                    "gap_budget_sec": 3.0,
                    "cumulative_min_sec": 24.0,
                    "high_severity_delta_deg": 6.0,
                    "high_severity_window_sec": 10.0
                }
            },
            "nudge_config": {
                "cooldown_done_sec": 1800.0,
                "cooldown_snooze_sec": 900.0,
                "dismiss_backoff_neck_deg": 5.0,
                "dismiss_backoff_torso_deg": 5.0,
                "dismiss_backoff_lateral_cm": 1.0,
                "dismiss_backoff_duration_sec": 3600.0,
                "dedupe_window_sec": 1200.0,
                "nudge_expiry_sec": 2700.0,
                "respect_dnd": True,
                "allow_stacking": False,
                "high_severity_bypass_dedupe": True
            },
            "system_config": {
                "target_fps": 8.0,
                "camera_index": 0,
                "ema_alpha": 0.3,
                "window_seconds": 60.0,
                "diagnostics_enabled": False
            }
        }
    
    def purge_config(self):
        """Delete configuration file (privacy purge)."""
        if self.config_path.exists():
            self.config_path.unlink()
