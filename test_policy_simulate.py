#!/usr/bin/env python3
"""
Test helper for simulating state transitions and testing notification policy.

Usage:
    python test_policy_simulate.py --state slouch --duration 40
    python test_policy_simulate.py --state forward_lean --severity high
"""

import argparse
import time
from datetime import datetime

from core import (
    StateTransitionEvent,
    StateConfig,
    NudgeConfig,
    NotificationPolicy,
    SensitivityPreset,
    CalibrationStorage
)


def simulate_transition(
    state: str,
    duration: float = 30.0,
    severity: str = "normal",
    dry_run: bool = False
):
    """
    Simulate a state transition and test policy response.
    
    Args:
        state: Target state (slouch, forward_lean, lateral_lean)
        duration: Time in previous state
        severity: normal or high (affects reason string)
        dry_run: If True, don't post actual notifications
    """
    # Load calibration
    storage = CalibrationStorage()
    baseline = storage.load_baseline()
    
    if not baseline:
        print("ERROR: No calibration found. Run dev_runner_calibrate.py first.")
        return
    
    # Create state config and policy
    state_config = StateConfig.from_preset(SensitivityPreset.SENSITIVE)
    nudge_config = NudgeConfig()
    nudge_config.respect_dnd = False  # Disable DND for testing
    
    policy = NotificationPolicy(
        state_config=state_config,
        nudge_config=nudge_config,
        dry_run=dry_run
    )
    
    # Build reason string
    if severity == "high":
        if state == "slouch":
            reason = f"High-severity slouch: Neck 28.4° > 18.8° for 8s"
        elif state == "forward_lean":
            reason = f"High-severity forward lean: Torso 20.3° > 10.3° for 8s"
        else:
            reason = f"High-severity lateral lean: 0.120 > 0.068 for 10s"
    else:
        if state == "slouch":
            reason = f"Slouch (majority): Neck 19.5° > 16.4° (73% of 30s, 22s total)"
        elif state == "forward_lean":
            reason = f"Forward lean (majority): Torso 12.1° > 10.3° (68% of 30s, 20s total)"
        else:
            reason = f"Lateral lean (majority): 0.075 > 0.068 (65% of 40s, 26s total)"
    
    # Create simulated event
    event = StateTransitionEvent(
        timestamp=datetime.now().isoformat(),
        from_state="good",
        to_state=state,
        reason=reason,
        time_in_previous_state=duration,
        metrics_snapshot={
            "neck_flexion": 19.5 if state == "slouch" else 8.4,
            "torso_flexion": 12.1 if state == "forward_lean" else 2.3,
            "lateral_lean": 0.075 if state == "lateral_lean" else 0.023,
            "confidence": 0.67
        }
    )
    
    print("=" * 80)
    print("SIMULATED STATE TRANSITION")
    print("=" * 80)
    print(f"State: {state.upper()}")
    print(f"Duration: {duration:.1f}s")
    print(f"Severity: {severity}")
    print(f"Reason: {reason}")
    print()
    
    # Pass to policy
    policy.on_state_transition(event, diagnostics=None)
    
    # Show policy status
    status = policy.get_policy_status()
    print()
    print("Policy Status:")
    print(f"  Cooldown: {status['cooldown_remaining_min']:.1f}m")
    print(f"  Snooze: {status['snooze_remaining_min']:.1f}m")
    print(f"  Backoff: {status['backoff_remaining_min']:.1f}m")
    print(f"  Last nudge: {status['last_nudge_min_ago']:.1f}m ago" if status['last_nudge_min_ago'] else "  Last nudge: None")
    print()
    
    # Simulate user actions
    print("Simulating user actions...")
    print("  (In real usage, these would come from notification clicks)")
    print()
    
    # Wait a moment
    time.sleep(2)
    
    # Show event log
    print("Recent events:")
    events = policy.event_logger.get_recent_events(limit=5)
    for evt in events:
        print(f"  [{evt['timestamp']}] {evt['event_type']}: {evt['state']} - {evt['reason']}")
    
    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Test notification policy with simulated transitions")
    parser.add_argument("--state", type=str, required=True,
                       choices=["slouch", "forward_lean", "lateral_lean"],
                       help="State to simulate")
    parser.add_argument("--duration", type=float, default=30.0,
                       help="Time in previous state (seconds)")
    parser.add_argument("--severity", type=str, default="normal",
                       choices=["normal", "high"],
                       help="Severity level")
    parser.add_argument("--dry-run", action="store_true",
                       help="Don't post actual notifications")
    
    args = parser.parse_args()
    
    simulate_transition(
        state=args.state,
        duration=args.duration,
        severity=args.severity,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
