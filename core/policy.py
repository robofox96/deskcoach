"""
Notification policy layer.

Consumes state transition events and decides when to nudge based on:
- Cooldowns (Done, Snooze)
- Temporary backoff (Dismiss)
- De-duplication
- DND/Focus mode
- State priority

PRIVACY: Only processes metrics, never frames.
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .state_machine_events import StateTransitionEvent
from .state_machine_config import StateConfig
from .nudge_config import NudgeConfig
from .notifications import NotificationEngine, NotificationAction
from .event_logger import EventLogger
from .metrics import PostureState


@dataclass
class QueuedNudge:
    """A nudge queued due to DND."""
    state: str
    reason: str
    queued_at: float
    expires_at: float
    thresholds: Dict[str, float]
    diagnostics: Optional[Dict[str, Any]] = None


class NotificationPolicy:
    """
    Notification policy engine.
    
    Decides when to nudge based on cooldowns, backoff, dedupe, and DND.
    Handles user actions (Done/Snooze/Dismiss) and applies appropriate logic.
    """
    
    def __init__(
        self,
        state_config: StateConfig,
        nudge_config: Optional[NudgeConfig] = None,
        notification_engine: Optional[NotificationEngine] = None,
        event_logger: Optional[EventLogger] = None,
        dry_run: bool = False
    ):
        """
        Initialize notification policy.
        
        Args:
            state_config: State machine configuration (for thresholds)
            nudge_config: Nudge policy configuration
            notification_engine: Notification engine
            event_logger: Event logger
            dry_run: If True, log decisions but don't post notifications
        """
        self.state_config = state_config
        self.nudge_config = nudge_config or NudgeConfig()
        self.notification_engine = notification_engine or NotificationEngine()
        self.event_logger = event_logger or EventLogger()
        self.dry_run = dry_run
        
        # State tracking
        self.last_nudge_time: Optional[float] = None
        self.last_nudge_state: Optional[str] = None
        self.last_nudge_per_state: Dict[str, float] = {}
        
        # Cooldowns
        self.cooldown_until: Optional[float] = None  # Global cooldown (Done)
        self.snooze_until: Optional[float] = None  # Snooze window
        
        # Temporary backoff (Dismiss)
        self.backoff_until: Optional[float] = None
        self.backoff_neck_delta: float = 0.0
        self.backoff_torso_delta: float = 0.0
        self.backoff_lateral_delta: float = 0.0
        
        # DND queue
        self.queued_nudge: Optional[QueuedNudge] = None
        
        # Diagnostics
        self.last_decision: Optional[Dict[str, Any]] = None
    
    def on_state_transition(
        self,
        event: StateTransitionEvent,
        diagnostics: Optional[Dict[str, Any]] = None
    ):
        """
        Handle a state transition event.
        
        Decides whether to nudge based on policy rules.
        
        Args:
            event: State transition event from state machine
            diagnostics: Optional diagnostic info from state machine
        """
        # Never nudge on PAUSED or GOOD states
        if event.to_state in ["paused", "good"]:
            return
        
        # Check if we should nudge
        decision = self._should_nudge(event, diagnostics)
        self.last_decision = decision
        
        if decision["should_nudge"]:
            self._post_nudge(event, diagnostics, decision)
        else:
            # Log suppression
            self.event_logger.log_suppressed(
                state=event.to_state,
                reason=event.reason,
                suppression_type=decision["suppression_reason"]
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Nudge suppressed: {decision['suppression_reason']}")
    
    def _should_nudge(
        self,
        event: StateTransitionEvent,
        diagnostics: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Decide if we should nudge for this transition.
        
        Returns:
            Dictionary with decision and reason
        """
        current_time = time.time()
        
        # Check global cooldown (Done)
        if self.cooldown_until and current_time < self.cooldown_until:
            remaining = self.cooldown_until - current_time
            return {
                "should_nudge": False,
                "suppression_reason": f"global_cooldown ({remaining/60:.1f}m remaining)"
            }
        
        # Check snooze window
        if self.snooze_until and current_time < self.snooze_until:
            remaining = self.snooze_until - current_time
            return {
                "should_nudge": False,
                "suppression_reason": f"snooze ({remaining/60:.1f}m remaining)"
            }
        
        # Check if notification engine has active notification
        # Clear stale notifications (after 10 seconds, macOS auto-dismisses)
        if self.notification_engine.has_active_notification():
            age = self.notification_engine.get_active_notification_age()
            if age and age > 10.0:  # 10 seconds timeout
                self.notification_engine.clear_active_notification()
        
        if not self.nudge_config.allow_stacking and self.notification_engine.has_active_notification():
            return {
                "should_nudge": False,
                "suppression_reason": "active_notification_exists"
            }
        
        # Check per-state dedupe window
        last_nudge_for_state = self.last_nudge_per_state.get(event.to_state)
        if last_nudge_for_state:
            time_since_last = current_time - last_nudge_for_state
            if time_since_last < self.nudge_config.dedupe_window_sec:
                # Check if this is high-severity and can bypass
                is_high_severity = "high-severity" in event.reason.lower()
                if not (is_high_severity and self.nudge_config.high_severity_bypass_dedupe):
                    remaining = self.nudge_config.dedupe_window_sec - time_since_last
                    return {
                        "should_nudge": False,
                        "suppression_reason": f"dedupe_window ({remaining/60:.1f}m remaining for {event.to_state})"
                    }
        
        # All checks passed
        return {
            "should_nudge": True,
            "suppression_reason": None
        }
    
    def _post_nudge(
        self,
        event: StateTransitionEvent,
        diagnostics: Optional[Dict[str, Any]],
        decision: Dict[str, Any]
    ):
        """Post a nudge notification."""
        current_time = time.time()
        
        # Get thresholds (with backoff if active)
        thresholds = self._get_effective_thresholds()
        
        # Build notification message
        title = self._get_notification_title(event.to_state)
        message = self._build_notification_message(event, diagnostics, thresholds)
        
        # Check DND
        if self.nudge_config.respect_dnd and self.notification_engine.is_dnd_active():
            # Queue the nudge
            expires_at = current_time + self.nudge_config.nudge_expiry_sec
            self.queued_nudge = QueuedNudge(
                state=event.to_state,
                reason=event.reason,
                queued_at=current_time,
                expires_at=expires_at,
                thresholds=thresholds,
                diagnostics=diagnostics
            )
            
            self.event_logger.log_queued_dnd(
                state=event.to_state,
                reason=event.reason,
                expires_at=expires_at
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Nudge queued (DND active), expires in {self.nudge_config.nudge_expiry_sec/60:.1f}m")
            
            return
        
        # Post notification
        if self.dry_run:
            print(f"  [POLICY] DRY RUN: Would post notification")
            print(f"    Title: {title}")
            print(f"    Message: {message}")
        else:
            # Try terminal-notifier first for action support
            print(f"  [POLICY] Attempting to post notification...")
            print(f"    Title: {title}")
            print(f"    Message: {message}")
            
            success = self.notification_engine.post_with_terminal_notifier(
                title=title,
                message=message,
                subtitle=None
            )
            
            if success:
                print(f"  [POLICY] ✅ Notification posted successfully!")
            else:
                print(f"  [POLICY] ❌ Failed to post notification")
                return
        
        # Update tracking
        self.last_nudge_time = current_time
        self.last_nudge_state = event.to_state
        self.last_nudge_per_state[event.to_state] = current_time
        
        # Log event
        self.event_logger.log_nudge(
            state=event.to_state,
            reason=event.reason,
            thresholds=thresholds,
            diagnostics=diagnostics
        )
        
        if not self.dry_run:
            print(f"  [POLICY] Nudge posted: {event.to_state}")
    
    def _get_notification_title(self, state: str) -> str:
        """Get notification title for state."""
        titles = {
            "slouch": "Posture Check: Slouching",
            "forward_lean": "Posture Check: Leaning Forward",
            "lateral_lean": "Posture Check: Leaning Sideways"
        }
        return titles.get(state, "Posture Check")
    
    def _build_notification_message(
        self,
        event: StateTransitionEvent,
        diagnostics: Optional[Dict[str, Any]],
        thresholds: Dict[str, float]
    ) -> str:
        """Build notification message with metrics and explanation."""
        # Extract metrics from event
        metrics = event.metrics_snapshot
        
        # Build message based on state
        if event.to_state == "slouch":
            neck = metrics.get("neck_flexion", 0)
            threshold = thresholds.get("neck", 0)
            message = f"Neck {neck:.1f}° > {threshold:.1f}°"
        elif event.to_state == "forward_lean":
            torso = metrics.get("torso_flexion", 0)
            threshold = thresholds.get("torso", 0)
            message = f"Torso {torso:.1f}° > {threshold:.1f}°"
        elif event.to_state == "lateral_lean":
            lateral = metrics.get("lateral_lean", 0)
            threshold = thresholds.get("lateral", 0)
            message = f"Lateral {lateral:.3f} > {threshold:.3f}"
        else:
            message = event.reason
        
        # Add diagnostics if available
        if diagnostics and event.to_state in diagnostics:
            diag = diagnostics[event.to_state]
            if "above_fraction" in diag:
                message += f" ({diag['above_fraction']:.0%} of last {diag.get('window_sec', 30):.0f}s)"
        
        return message
    
    def _get_effective_thresholds(self) -> Dict[str, float]:
        """Get effective thresholds (with backoff if active)."""
        current_time = time.time()
        
        # Base thresholds from config
        # Note: These are deltas, not absolute thresholds
        # Actual thresholds are baseline + delta
        neck_delta = self.state_config.slouch_threshold_deg
        torso_delta = self.state_config.forward_lean_threshold_deg
        lateral_delta = self.state_config.lateral_lean_threshold_cm
        
        # Apply backoff if active
        if self.backoff_until and current_time < self.backoff_until:
            neck_delta += self.backoff_neck_delta
            torso_delta += self.backoff_torso_delta
            lateral_delta += self.backoff_lateral_delta
        
        return {
            "neck": neck_delta,
            "torso": torso_delta,
            "lateral": lateral_delta
        }
    
    def on_user_action(self, action: NotificationAction):
        """
        Handle user action on notification.
        
        Args:
            action: User action (Done/Snooze/Dismiss)
        """
        current_time = time.time()
        state = self.last_nudge_state or "unknown"
        
        if action == NotificationAction.DONE:
            # Set global cooldown
            self.cooldown_until = current_time + self.nudge_config.cooldown_done_sec
            
            self.event_logger.log_action(
                action="done",
                state=state,
                cooldown_until=self.cooldown_until
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Done action: cooldown for {self.nudge_config.cooldown_done_sec/60:.1f}m")
        
        elif action == NotificationAction.SNOOZE:
            # Set snooze window
            self.snooze_until = current_time + self.nudge_config.cooldown_snooze_sec
            
            self.event_logger.log_action(
                action="snooze",
                state=state,
                cooldown_until=self.snooze_until
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Snooze action: suppressing for {self.nudge_config.cooldown_snooze_sec/60:.1f}m")
        
        elif action == NotificationAction.DISMISS:
            # Set temporary backoff
            self.backoff_until = current_time + self.nudge_config.dismiss_backoff_duration_sec
            self.backoff_neck_delta = self.nudge_config.dismiss_backoff_neck_deg
            self.backoff_torso_delta = self.nudge_config.dismiss_backoff_torso_deg
            self.backoff_lateral_delta = self.nudge_config.dismiss_backoff_lateral_cm
            
            self.event_logger.log_action(
                action="dismiss",
                state=state,
                backoff_until=self.backoff_until
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Dismiss action: backoff for {self.nudge_config.dismiss_backoff_duration_sec/60:.1f}m")
                print(f"    Thresholds: neck +{self.backoff_neck_delta}°, torso +{self.backoff_torso_delta}°, lateral +{self.backoff_lateral_delta}cm")
        
        # Clear active notification
        self.notification_engine.clear_active_notification()
    
    def check_dnd_queue(self):
        """
        Check if DND has ended and deliver queued nudge.
        
        Should be called periodically (e.g., every few seconds).
        """
        if not self.queued_nudge:
            return
        
        current_time = time.time()
        
        # Check if expired
        if current_time >= self.queued_nudge.expires_at:
            self.event_logger.log_expired_dnd(
                state=self.queued_nudge.state,
                reason=self.queued_nudge.reason
            )
            
            if not self.dry_run:
                print(f"  [POLICY] Queued nudge expired (DND lasted too long)")
            
            self.queued_nudge = None
            return
        
        # Check if DND has ended
        if not self.notification_engine.is_dnd_active():
            # Deliver queued nudge
            queued_duration = current_time - self.queued_nudge.queued_at
            
            title = self._get_notification_title(self.queued_nudge.state)
            message = f"{self.queued_nudge.reason} (queued {queued_duration/60:.1f}m ago)"
            
            if self.dry_run:
                print(f"  [POLICY] DRY RUN: Would deliver queued notification")
            else:
                self.notification_engine.post_with_terminal_notifier(
                    title=title,
                    message=message,
                    subtitle="DND ended"
                )
            
            self.event_logger.log_delivered_dnd(
                state=self.queued_nudge.state,
                reason=self.queued_nudge.reason,
                queued_duration_sec=queued_duration
            )
            
            # Update tracking
            self.last_nudge_time = current_time
            self.last_nudge_state = self.queued_nudge.state
            self.last_nudge_per_state[self.queued_nudge.state] = current_time
            
            if not self.dry_run:
                print(f"  [POLICY] Queued nudge delivered (DND ended)")
            
            self.queued_nudge = None
    
    def get_policy_status(self) -> Dict[str, Any]:
        """
        Get current policy status for diagnostics.
        
        Returns:
            Dictionary with cooldown/snooze/backoff status
        """
        current_time = time.time()
        
        status = {
            "cooldown_remaining_min": 0.0,
            "snooze_remaining_min": 0.0,
            "backoff_remaining_min": 0.0,
            "last_nudge_min_ago": None,
            "active_state": self.last_nudge_state,
            "queued_nudge": self.queued_nudge is not None
        }
        
        if self.cooldown_until and current_time < self.cooldown_until:
            status["cooldown_remaining_min"] = (self.cooldown_until - current_time) / 60
        
        if self.snooze_until and current_time < self.snooze_until:
            status["snooze_remaining_min"] = (self.snooze_until - current_time) / 60
        
        if self.backoff_until and current_time < self.backoff_until:
            status["backoff_remaining_min"] = (self.backoff_until - current_time) / 60
        
        if self.last_nudge_time:
            status["last_nudge_min_ago"] = (current_time - self.last_nudge_time) / 60
        
        return status
    
    def get_effective_thresholds_with_baselines(
        self,
        baselines: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Get effective absolute thresholds (baseline + delta + backoff).
        
        Args:
            baselines: Current drift baselines from state machine
            
        Returns:
            Dictionary with absolute thresholds
        """
        deltas = self._get_effective_thresholds()
        
        return {
            "neck": baselines.get("neck", 0) + deltas["neck"],
            "torso": baselines.get("torso", 0) + deltas["torso"],
            "lateral": deltas["lateral"]  # Lateral is already computed as absolute
        }
