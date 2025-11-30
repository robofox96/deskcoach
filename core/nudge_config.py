"""
Notification policy configuration.
"""

from dataclasses import dataclass


@dataclass
class NudgeConfig:
    """
    Configuration for notification policy and cooldowns.
    
    All durations in seconds. User-tunable via UI later.
    """
    # Cooldowns
    cooldown_done_sec: float = 1800.0  # 30 min after Done action
    cooldown_snooze_sec: float = 900.0  # 15 min after Snooze action
    
    # Dismiss backoff (temporary threshold increase)
    dismiss_backoff_neck_deg: float = 5.0  # Add to neck threshold
    dismiss_backoff_torso_deg: float = 5.0  # Add to torso threshold
    dismiss_backoff_lateral_cm: float = 1.0  # Add to lateral threshold
    dismiss_backoff_duration_sec: float = 3600.0  # 60 min
    
    # De-duplication (per-state)
    dedupe_window_sec: float = 1200.0  # 20 min - don't re-nudge same state
    
    # DND/Focus handling
    nudge_expiry_sec: float = 2700.0  # 45 min - expire queued nudges
    respect_dnd: bool = True  # Respect system DND/Focus modes
    
    # One active nudge at a time
    allow_stacking: bool = False  # Only one notification active
    
    # High-severity override (can bypass dedupe window)
    high_severity_bypass_dedupe: bool = True
