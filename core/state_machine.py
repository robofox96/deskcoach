"""
Posture state machine with majority/cumulative sustain detection.

Implements states: GOOD, SLOUCH, FORWARD_LEAN, LATERAL_LEAN, PAUSED
Uses calibrated baselines with configurable thresholds.
Includes majority-based detection, grace gaps, high-severity shortcuts, and baseline drift.

PRIVACY: Only processes metrics, never frames.
"""

import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from .metrics import PostureMetrics, PostureState
from .storage import CalibrationBaseline
from .state_machine_config import StateConfig, SensitivityPreset, SustainPolicy
from .state_machine_events import StateTransitionEvent
from .state_machine_window import ConditionWindow


class PostureStateMachine:
    """
    State machine for posture monitoring with majority/cumulative sustain detection.
    
    States:
    - GOOD: Neutral posture within thresholds
    - SLOUCH: Neck flexion exceeds threshold (majority/cumulative/high-severity)
    - FORWARD_LEAN: Torso flexion exceeds threshold (majority/cumulative/high-severity)
    - LATERAL_LEAN: Shoulder asymmetry exceeds threshold (majority/cumulative/high-severity)
    - PAUSED: Low confidence or no pose detected
    
    Detection Features:
    - Majority-based: >=60% of samples above threshold in window
    - Cumulative: Total time above threshold >= threshold
    - Grace gaps: Brief dips (<=3s) don't reset detection
    - High-severity shortcuts: Very bad posture triggers immediately
    - Recovery windows with majority-below logic
    - Baseline drift correction (slow EMA in GOOD state)
    """
    
    def __init__(
        self,
        baseline: CalibrationBaseline,
        config: Optional[StateConfig] = None
    ):
        """
        Initialize state machine.
        
        Args:
            baseline: Calibrated baseline values
            config: State machine configuration (uses defaults if None)
        """
        self.baseline = baseline
        self.config = config or StateConfig()
        
        # Current state
        self.current_state = PostureState.GOOD
        self.state_entered_at = time.time()
        
        # Condition windows for tracking
        self.slouch_window = ConditionWindow()
        self.forward_lean_window = ConditionWindow()
        self.lateral_lean_window = ConditionWindow()
        self.recovery_window = ConditionWindow()
        
        # High-severity tracking
        self.high_severity_slouch_start: Optional[float] = None
        self.high_severity_forward_start: Optional[float] = None
        self.high_severity_lateral_start: Optional[float] = None
        
        # Event history
        self.transition_events: List[StateTransitionEvent] = []
        
        # Drifting baselines (updated slowly in GOOD state)
        self.drift_neck_baseline = baseline.neck_flexion_baseline
        self.drift_torso_baseline = baseline.torso_flexion_baseline
        self.drift_lateral_baseline = baseline.lateral_lean_baseline
        
        # Compute lateral threshold in pixels (scale-adjusted)
        self.lateral_threshold_pixels = self._compute_lateral_threshold_pixels()
    
    def _compute_lateral_threshold_pixels(self) -> float:
        """
        Compute lateral threshold in pixels from cm using shoulder width.
        
        Assumption: shoulder_width_proxy from calibration represents typical
        shoulder distance in normalized coordinates. We convert the cm threshold
        to a proportional increase in the lateral lean metric.
        
        Formula:
        - Average shoulder width ~40cm
        - threshold_cm / 40cm gives proportional increase
        - Apply to baseline: baseline + (baseline * ratio * 2.0)
        
        If actual shoulder width in pixels was captured during calibration,
        this can be refined to: threshold_cm / shoulder_width_cm * shoulder_width_pixels
        
        Returns:
            Lateral threshold in pixels (normalized coordinates)
        """
        # Simple ratio-based conversion (can be refined with actual shoulder width)
        typical_shoulder_width_cm = 40.0
        ratio = self.config.lateral_lean_threshold_cm / typical_shoulder_width_cm
        
        # Apply ratio to baseline to get absolute threshold
        # Factor of 2.0 accounts for the normalized metric scaling
        threshold_pixels = self.drift_lateral_baseline + (self.drift_lateral_baseline * ratio * 2.0)
        
        # Fallback: if baseline is very small, use absolute minimum
        if threshold_pixels < 0.05:
            threshold_pixels = 0.05
        
        return threshold_pixels
    
    def update(self, metrics: PostureMetrics) -> Optional[StateTransitionEvent]:
        """
        Update state machine with new metrics.
        
        Args:
            metrics: Current posture metrics
            
        Returns:
            StateTransitionEvent if state changed, None otherwise
        """
        current_time = time.time()
        
        # Check confidence first
        if metrics.confidence < self.config.confidence_threshold:
            return self._transition_to(PostureState.PAUSED, "Low confidence", metrics)
        
        # If currently PAUSED and confidence recovered, return to GOOD
        if self.current_state == PostureState.PAUSED:
            return self._transition_to(PostureState.GOOD, "Confidence recovered", metrics)
        
        # Update condition windows
        self._update_condition_windows(metrics, current_time)
        
        # Check for issue conditions
        slouch_result = self._check_slouch_condition(metrics, current_time)
        forward_result = self._check_forward_lean_condition(metrics, current_time)
        lateral_result = self._check_lateral_lean_condition(metrics, current_time)
        
        # Determine target state based on priority (slouch > forward > lateral)
        if slouch_result["triggered"]:
            target_state = PostureState.SLOUCH
            reason = slouch_result["reason"]
        elif forward_result["triggered"]:
            target_state = PostureState.FORWARD_LEAN
            reason = forward_result["reason"]
        elif lateral_result["triggered"]:
            target_state = PostureState.LATERAL_LEAN
            reason = lateral_result["reason"]
        else:
            target_state = PostureState.GOOD
            reason = ""
        
        # Handle state transitions
        event = self._handle_state_transition(metrics, target_state, reason, current_time)
        
        # Apply baseline drift if in GOOD state
        if self.current_state == PostureState.GOOD:
            self._apply_baseline_drift(metrics)
            # Update lateral threshold as baseline drifts
            self.lateral_threshold_pixels = self._compute_lateral_threshold_pixels()
        
        return event
    
    def _update_condition_windows(self, metrics: PostureMetrics, current_time: float):
        """Update all condition windows with current metrics."""
        # Slouch (neck)
        neck_threshold = self.drift_neck_baseline + self.config.slouch_threshold_deg
        self.slouch_window.add(current_time, metrics.neck_flexion > neck_threshold)
        
        # Forward lean (torso)
        torso_threshold = self.drift_torso_baseline + self.config.forward_lean_threshold_deg
        self.forward_lean_window.add(current_time, metrics.torso_flexion > torso_threshold)
        
        # Lateral lean
        self.lateral_lean_window.add(current_time, metrics.lateral_lean > self.lateral_threshold_pixels)
        
        # Recovery window (if in issue state)
        if self.current_state not in [PostureState.GOOD, PostureState.PAUSED]:
            # Track if currently below threshold
            below_neck = metrics.neck_flexion <= neck_threshold
            below_torso = metrics.torso_flexion <= torso_threshold
            below_lateral = metrics.lateral_lean <= self.lateral_threshold_pixels
            
            # For recovery, track samples still above threshold (inverse logic)
            if self.current_state == PostureState.SLOUCH:
                self.recovery_window.add(current_time, not below_neck)
            elif self.current_state == PostureState.FORWARD_LEAN:
                self.recovery_window.add(current_time, not below_torso)
            elif self.current_state == PostureState.LATERAL_LEAN:
                self.recovery_window.add(current_time, not below_lateral)
    
    def _check_slouch_condition(self, metrics: PostureMetrics, current_time: float) -> Dict[str, Any]:
        """Check if slouch condition is met."""
        policy = self.config.slouch_policy
        threshold = self.drift_neck_baseline + self.config.slouch_threshold_deg
        high_severity_threshold = self.drift_neck_baseline + policy.high_severity_delta_deg
        
        # Check high-severity shortcut
        if metrics.neck_flexion > high_severity_threshold:
            if self.high_severity_slouch_start is None:
                self.high_severity_slouch_start = current_time
            elif current_time - self.high_severity_slouch_start >= policy.high_severity_window_sec:
                return {
                    "triggered": True,
                    "reason": f"High-severity slouch: Neck {metrics.neck_flexion:.1f}° > {high_severity_threshold:.1f}° for {policy.high_severity_window_sec:.0f}s"
                }
        else:
            self.high_severity_slouch_start = None
        
        # Check majority/cumulative logic
        stats = self.slouch_window.get_stats(current_time, policy.window_sec)
        
        # Path 1: Majority with grace gap
        majority_met = (stats["above_fraction"] >= policy.majority_fraction and 
                       stats["max_gap_sec"] <= policy.gap_budget_sec)
        
        # Path 2: Cumulative time
        cumulative_met = stats["cumulative_above_sec"] >= policy.cumulative_min_sec
        
        if majority_met or cumulative_met:
            path = "majority" if majority_met else "cumulative"
            return {
                "triggered": True,
                "reason": f"Slouch ({path}): Neck {metrics.neck_flexion:.1f}° > {threshold:.1f}° "
                         f"({stats['above_fraction']:.0%} of {policy.window_sec:.0f}s, "
                         f"{stats['cumulative_above_sec']:.0f}s total)",
                "stats": stats
            }
        
        return {"triggered": False, "stats": stats}
    
    def _check_forward_lean_condition(self, metrics: PostureMetrics, current_time: float) -> Dict[str, Any]:
        """Check if forward lean condition is met."""
        policy = self.config.forward_lean_policy
        threshold = self.drift_torso_baseline + self.config.forward_lean_threshold_deg
        high_severity_threshold = self.drift_torso_baseline + policy.high_severity_delta_deg
        
        # Check high-severity shortcut
        if metrics.torso_flexion > high_severity_threshold:
            if self.high_severity_forward_start is None:
                self.high_severity_forward_start = current_time
            elif current_time - self.high_severity_forward_start >= policy.high_severity_window_sec:
                return {
                    "triggered": True,
                    "reason": f"High-severity forward lean: Torso {metrics.torso_flexion:.1f}° > {high_severity_threshold:.1f}° for {policy.high_severity_window_sec:.0f}s"
                }
        else:
            self.high_severity_forward_start = None
        
        # Check majority/cumulative logic
        stats = self.forward_lean_window.get_stats(current_time, policy.window_sec)
        
        majority_met = (stats["above_fraction"] >= policy.majority_fraction and 
                       stats["max_gap_sec"] <= policy.gap_budget_sec)
        cumulative_met = stats["cumulative_above_sec"] >= policy.cumulative_min_sec
        
        if majority_met or cumulative_met:
            path = "majority" if majority_met else "cumulative"
            return {
                "triggered": True,
                "reason": f"Forward lean ({path}): Torso {metrics.torso_flexion:.1f}° > {threshold:.1f}° "
                         f"({stats['above_fraction']:.0%} of {policy.window_sec:.0f}s, "
                         f"{stats['cumulative_above_sec']:.0f}s total)",
                "stats": stats
            }
        
        return {"triggered": False, "stats": stats}
    
    def _check_lateral_lean_condition(self, metrics: PostureMetrics, current_time: float) -> Dict[str, Any]:
        """Check if lateral lean condition is met."""
        policy = self.config.lateral_lean_policy
        threshold = self.lateral_threshold_pixels
        
        # High-severity threshold for lateral (using cm-based delta)
        high_severity_ratio = policy.high_severity_delta_deg / 40.0  # cm to ratio
        high_severity_threshold = self.drift_lateral_baseline + (self.drift_lateral_baseline * high_severity_ratio * 2.0)
        
        # Check high-severity shortcut
        if metrics.lateral_lean > high_severity_threshold:
            if self.high_severity_lateral_start is None:
                self.high_severity_lateral_start = current_time
            elif current_time - self.high_severity_lateral_start >= policy.high_severity_window_sec:
                return {
                    "triggered": True,
                    "reason": f"High-severity lateral lean: {metrics.lateral_lean:.3f} > {high_severity_threshold:.3f} for {policy.high_severity_window_sec:.0f}s"
                }
        else:
            self.high_severity_lateral_start = None
        
        # Check majority/cumulative logic
        stats = self.lateral_lean_window.get_stats(current_time, policy.window_sec)
        
        majority_met = (stats["above_fraction"] >= policy.majority_fraction and 
                       stats["max_gap_sec"] <= policy.gap_budget_sec)
        cumulative_met = stats["cumulative_above_sec"] >= policy.cumulative_min_sec
        
        if majority_met or cumulative_met:
            path = "majority" if majority_met else "cumulative"
            return {
                "triggered": True,
                "reason": f"Lateral lean ({path}): {metrics.lateral_lean:.3f} > {threshold:.3f} "
                         f"({stats['above_fraction']:.0%} of {policy.window_sec:.0f}s, "
                         f"{stats['cumulative_above_sec']:.0f}s total)",
                "stats": stats
            }
        
        return {"triggered": False, "stats": stats}
    
    def _handle_state_transition(
        self,
        metrics: PostureMetrics,
        target_state: PostureState,
        reason: str,
        current_time: float
    ) -> Optional[StateTransitionEvent]:
        """Handle state transitions with recovery logic."""
        # If already in target state, no transition
        if self.current_state == target_state:
            # Reset recovery window if staying in issue state
            if target_state not in [PostureState.GOOD, PostureState.PAUSED]:
                self.recovery_window.clear()
            return None
        
        # Transitioning to an issue state (GOOD -> issue)
        if self.current_state == PostureState.GOOD and target_state != PostureState.GOOD:
            return self._transition_to(target_state, reason, metrics)
        
        # Transitioning from issue state to GOOD (recovery)
        if self.current_state != PostureState.GOOD and target_state == PostureState.GOOD:
            # Check recovery window
            recovery_stats = self.recovery_window.get_stats(current_time, self.config.recovery_window_sec)
            
            # Recovery requires majority BELOW threshold (inverse logic)
            # above_fraction in recovery_window tracks samples still above threshold
            # We want < (1 - majority_fraction) above = majority below
            recovery_threshold = 1.0 - self.config.recovery_majority_fraction
            
            if recovery_stats["above_fraction"] < recovery_threshold:
                reason = f"Recovery: Metrics below threshold for {self.config.recovery_window_sec:.0f}s " \
                        f"({(1-recovery_stats['above_fraction']):.0%} below)"
                self.recovery_window.clear()
                return self._transition_to(target_state, reason, metrics)
            
            # Still in recovery, no transition yet
            return None
        
        # Transitioning between issue states (e.g., SLOUCH -> FORWARD_LEAN)
        if self.current_state != PostureState.GOOD and target_state != PostureState.GOOD:
            # Direct transition if new condition is met
            self.recovery_window.clear()
            return self._transition_to(target_state, reason, metrics)
        
        return None
    
    def _transition_to(
        self,
        new_state: PostureState,
        reason: str,
        metrics: Optional[PostureMetrics] = None
    ) -> Optional[StateTransitionEvent]:
        """Transition to a new state and emit event."""
        if new_state == self.current_state:
            return None
        
        current_time = time.time()
        time_in_state = current_time - self.state_entered_at
        
        # Create transition event
        event = StateTransitionEvent(
            timestamp=datetime.now().isoformat(),
            from_state=self.current_state.value,
            to_state=new_state.value,
            reason=reason,
            time_in_previous_state=time_in_state,
            metrics_snapshot={
                "neck_flexion": metrics.neck_flexion if metrics else 0.0,
                "torso_flexion": metrics.torso_flexion if metrics else 0.0,
                "lateral_lean": metrics.lateral_lean if metrics else 0.0,
                "confidence": metrics.confidence if metrics else 0.0
            }
        )
        
        # Update state
        self.current_state = new_state
        self.state_entered_at = current_time
        
        # Store event
        self.transition_events.append(event)
        
        # Reset windows on transition
        if new_state == PostureState.GOOD:
            self.slouch_window.clear()
            self.forward_lean_window.clear()
            self.lateral_lean_window.clear()
            self.recovery_window.clear()
            self.high_severity_slouch_start = None
            self.high_severity_forward_start = None
            self.high_severity_lateral_start = None
        
        return event
    
    def _apply_baseline_drift(self, metrics: PostureMetrics):
        """Apply slow EMA drift to baselines while in GOOD state."""
        alpha = self.config.drift_alpha
        
        self.drift_neck_baseline = (
            alpha * metrics.neck_flexion + (1 - alpha) * self.drift_neck_baseline
        )
        self.drift_torso_baseline = (
            alpha * metrics.torso_flexion + (1 - alpha) * self.drift_torso_baseline
        )
        self.drift_lateral_baseline = (
            alpha * metrics.lateral_lean + (1 - alpha) * self.drift_lateral_baseline
        )
    
    def get_current_state(self) -> PostureState:
        """Get current state."""
        return self.current_state
    
    def get_time_in_state(self) -> float:
        """Get time spent in current state (seconds)."""
        return time.time() - self.state_entered_at
    
    def get_condition_diagnostics(self) -> Dict[str, Any]:
        """
        Get diagnostic information about condition windows.
        
        Returns:
            Dictionary with stats for each condition type
        """
        current_time = time.time()
        
        slouch_stats = self.slouch_window.get_stats(current_time, self.config.slouch_policy.window_sec)
        forward_stats = self.forward_lean_window.get_stats(current_time, self.config.forward_lean_policy.window_sec)
        lateral_stats = self.lateral_lean_window.get_stats(current_time, self.config.lateral_lean_policy.window_sec)
        
        return {
            "slouch": {
                **slouch_stats,
                "threshold": self.drift_neck_baseline + self.config.slouch_threshold_deg,
                "baseline": self.drift_neck_baseline,
                "delta": self.config.slouch_threshold_deg
            },
            "forward_lean": {
                **forward_stats,
                "threshold": self.drift_torso_baseline + self.config.forward_lean_threshold_deg,
                "baseline": self.drift_torso_baseline,
                "delta": self.config.forward_lean_threshold_deg
            },
            "lateral_lean": {
                **lateral_stats,
                "threshold": self.lateral_threshold_pixels,
                "baseline": self.drift_lateral_baseline,
                "delta_cm": self.config.lateral_lean_threshold_cm
            }
        }
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of current state.
        
        Returns:
            Dictionary with state info
        """
        return {
            "current_state": self.current_state.value,
            "time_in_state": self.get_time_in_state(),
            "state_entered_at": datetime.fromtimestamp(self.state_entered_at).isoformat(),
            "transition_count": len(self.transition_events),
            "preset": self.config.preset.value,
            "drift_baselines": {
                "neck": self.drift_neck_baseline,
                "torso": self.drift_torso_baseline,
                "lateral": self.drift_lateral_baseline
            },
            "thresholds": {
                "slouch": self.drift_neck_baseline + self.config.slouch_threshold_deg,
                "forward_lean": self.drift_torso_baseline + self.config.forward_lean_threshold_deg,
                "lateral_lean": self.lateral_threshold_pixels
            }
        }
    
    def get_state_counts(self) -> Dict[str, int]:
        """
        Get count of transitions to each state.
        
        Returns:
            Dictionary mapping state name to count
        """
        counts = {
            "good": 0,
            "slouch": 0,
            "forward_lean": 0,
            "lateral_lean": 0,
            "paused": 0
        }
        
        for event in self.transition_events:
            counts[event.to_state] = counts.get(event.to_state, 0) + 1
        
        return counts
    
    def get_last_transition(self) -> Optional[StateTransitionEvent]:
        """Get the most recent state transition event."""
        return self.transition_events[-1] if self.transition_events else None


# Re-export for convenience
__all__ = [
    "PostureStateMachine",
    "StateTransitionEvent",
    "StateConfig",
    "SensitivityPreset",
    "SustainPolicy"
]
