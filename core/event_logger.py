"""
Event logger for notification policy decisions.

Logs nudges, actions, cooldowns, and policy decisions.
PRIVACY: Only logs metrics and text, never frames.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class EventLogger:
    """
    Logger for notification policy events.
    
    Logs to JSONL format (one JSON object per line).
    Privacy-safe: only metrics and text, no frames.
    """
    
    def __init__(self, log_path: Optional[str] = None):
        """
        Initialize event logger.
        
        Args:
            log_path: Path to log file (default: storage/events.jsonl)
        """
        if log_path is None:
            log_path = "storage/events.jsonl"
        
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(
        self,
        event_type: str,
        state: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a notification policy event.
        
        Args:
            event_type: Type of event (nudged, action_done, action_snooze, etc.)
            state: Posture state at time of event
            reason: Brief reason string
            metadata: Additional metadata (cooldowns, thresholds, etc.)
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "unix_time": time.time(),
            "event_type": event_type,
            "state": state,
            "reason": reason,
            "metadata": metadata or {}
        }
        
        # Append to JSONL file
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def log_nudge(
        self,
        state: str,
        reason: str,
        thresholds: Dict[str, float],
        diagnostics: Optional[Dict[str, Any]] = None
    ):
        """Log a nudge event."""
        self.log_event(
            event_type="nudged",
            state=state,
            reason=reason,
            metadata={
                "thresholds": thresholds,
                "diagnostics": diagnostics
            }
        )
    
    def log_action(
        self,
        action: str,
        state: str,
        cooldown_until: Optional[float] = None,
        backoff_until: Optional[float] = None
    ):
        """Log a user action (done/snooze/dismiss)."""
        metadata = {}
        if cooldown_until:
            metadata["cooldown_until"] = cooldown_until
            metadata["cooldown_remaining_sec"] = max(0, cooldown_until - time.time())
        if backoff_until:
            metadata["backoff_until"] = backoff_until
            metadata["backoff_remaining_sec"] = max(0, backoff_until - time.time())
        
        self.log_event(
            event_type=f"action_{action}",
            state=state,
            reason=f"User clicked {action}",
            metadata=metadata
        )
    
    def log_suppressed(
        self,
        state: str,
        reason: str,
        suppression_type: str
    ):
        """Log a suppressed nudge (cooldown, snooze, dedupe, etc.)."""
        self.log_event(
            event_type="suppressed",
            state=state,
            reason=reason,
            metadata={"suppression_type": suppression_type}
        )
    
    def log_queued_dnd(
        self,
        state: str,
        reason: str,
        expires_at: float
    ):
        """Log a nudge queued due to DND."""
        self.log_event(
            event_type="queued_under_dnd",
            state=state,
            reason=reason,
            metadata={
                "expires_at": expires_at,
                "expires_in_sec": max(0, expires_at - time.time())
            }
        )
    
    def log_expired_dnd(
        self,
        state: str,
        reason: str
    ):
        """Log an expired queued nudge."""
        self.log_event(
            event_type="expired_under_dnd",
            state=state,
            reason=reason,
            metadata={}
        )
    
    def log_delivered_dnd(
        self,
        state: str,
        reason: str,
        queued_duration_sec: float
    ):
        """Log a nudge delivered after DND ended."""
        self.log_event(
            event_type="delivered_after_dnd",
            state=state,
            reason=reason,
            metadata={"queued_duration_sec": queued_duration_sec}
        )
    
    def get_recent_events(self, limit: int = 100) -> list:
        """
        Get recent events from log.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self.log_path.exists():
            return []
        
        events = []
        with open(self.log_path, "r") as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return events[-limit:]
    
    def purge_logs(self):
        """Delete all logged events (privacy purge)."""
        if self.log_path.exists():
            self.log_path.unlink()
