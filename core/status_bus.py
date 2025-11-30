"""
Status Bus - IPC bridge for live status updates.

Publishes current pose loop state to storage/status.json for UI consumption.
PRIVACY: No frames, only metrics and state.
"""

import json
import os
import time
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Callable
from pathlib import Path


@dataclass
class StatusSnapshot:
    """
    Single snapshot of current system state.
    
    PRIVACY: Contains only metrics (angles, timestamps, booleans).
    No frames, no images, no video.
    """
    # Timestamp
    ts_unix: float
    
    # State machine
    state: str  # "good", "slouch", "forward_lean", "lateral_lean", "paused"
    time_in_state_sec: float
    confidence: float
    fps: float
    
    # Current metrics
    metrics: Dict[str, float]  # {neck_deg, torso_deg, lateral}
    
    # Absolute thresholds (baseline + delta)
    thresholds: Dict[str, float]  # {neck_abs_deg, torso_abs_deg, lateral_abs}
    
    # Configuration
    preset: str  # "sensitive", "standard", "conservative"
    
    # Detection diagnostics
    detection_path: str  # "majority", "cumulative", "high_severity", "none"
    window_stats: Dict[str, Any]  # {above_fraction, cumulative_above_sec, max_gap_sec}
    
    # Policy status
    policy: Dict[str, Any]  # {cooldown_sec_left, snooze_sec_left, backoff_sec_left, dnd_queued_count, last_nudge_age_sec}


class StatusBus:
    """
    Background publisher that writes status snapshots to JSON file.
    
    Thread-safe, atomic writes, best-effort delivery.
    """
    
    def __init__(
        self,
        status_file: str = "storage/status.json",
        update_interval_sec: float = 1.0
    ):
        """
        Initialize status bus.
        
        Args:
            status_file: Path to status JSON file
            update_interval_sec: How often to publish (default: 1 Hz)
        """
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.update_interval_sec = update_interval_sec
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._snapshot_provider: Optional[Callable[[], Optional[StatusSnapshot]]] = None
        
        self._error_count = 0
        self._last_error_time = 0.0
        self._backoff_sec = 1.0
    
    def set_snapshot_provider(self, provider: Callable[[], Optional[StatusSnapshot]]):
        """
        Set the callback that provides status snapshots.
        
        Args:
            provider: Function that returns current StatusSnapshot or None
        """
        self._snapshot_provider = provider
    
    def start(self):
        """Start the publisher thread."""
        if self._running:
            return
        
        if not self._snapshot_provider:
            raise ValueError("Must set snapshot provider before starting")
        
        self._running = True
        self._thread = threading.Thread(target=self._publish_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the publisher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
    
    def _publish_loop(self):
        """Main publisher loop (runs in background thread)."""
        while self._running:
            try:
                # Get current snapshot
                snapshot = self._snapshot_provider()
                
                if snapshot:
                    # Write atomically
                    self._write_snapshot(snapshot)
                    
                    # Reset error tracking on success
                    self._error_count = 0
                    self._backoff_sec = 1.0
                
                # Sleep until next update
                time.sleep(self.update_interval_sec)
                
            except Exception as e:
                # Best-effort: log error but keep running
                self._error_count += 1
                current_time = time.time()
                
                # Only log errors occasionally to avoid spam
                if current_time - self._last_error_time > 10.0:
                    print(f"[STATUS_BUS] Error publishing status: {e}")
                    self._last_error_time = current_time
                
                # Exponential backoff on repeated errors
                if self._error_count > 3:
                    self._backoff_sec = min(self._backoff_sec * 2, 30.0)
                    time.sleep(self._backoff_sec)
                else:
                    time.sleep(self.update_interval_sec)
    
    def _write_snapshot(self, snapshot: StatusSnapshot):
        """
        Write snapshot to file atomically.
        
        Uses temp file + os.replace() to ensure atomic write.
        
        Args:
            snapshot: StatusSnapshot to write
        """
        # Convert to dict
        data = asdict(snapshot)
        
        # Serialize to JSON
        json_str = json.dumps(data, indent=2)
        
        # Check size (should be < 5 KB)
        size_kb = len(json_str.encode('utf-8')) / 1024
        if size_kb > 5.0:
            print(f"[STATUS_BUS] Warning: Status JSON is {size_kb:.1f} KB (> 5 KB limit)")
        
        # Write to temp file
        temp_file = self.status_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            f.write(json_str)
        
        # Atomic replace
        os.replace(temp_file, self.status_file)


def create_snapshot_from_pose_loop(
    pose_loop,
    state_machine,
    policy_engine,
    preset: str
) -> Optional[StatusSnapshot]:
    """
    Create StatusSnapshot from current pose loop state.
    
    Args:
        pose_loop: PoseLoop instance
        state_machine: PostureStateMachine instance
        policy_engine: NotificationPolicy instance
        preset: Current sensitivity preset name
        
    Returns:
        StatusSnapshot or None if not ready
    """
    try:
        # Get current state
        current_state = state_machine.current_state
        time_in_state = time.time() - state_machine.state_entered_at
        
        # Get latest metrics (smoothed)
        neck_values = pose_loop.neck_buffer.get_values()
        torso_values = pose_loop.torso_buffer.get_values()
        lateral_values = pose_loop.lateral_buffer.get_values()
        
        if not neck_values or not torso_values or not lateral_values:
            return None
        
        neck_deg = neck_values[-1]
        torso_deg = torso_values[-1]
        lateral = lateral_values[-1]
        
        # Get confidence
        confidence = pose_loop.last_confidence if hasattr(pose_loop, 'last_confidence') else 0.0
        
        # Get FPS
        fps = pose_loop.actual_fps if hasattr(pose_loop, 'actual_fps') else 0.0
        
        # Get absolute thresholds
        baseline = state_machine.baseline
        config = state_machine.config
        
        neck_threshold = baseline.neck_flexion_baseline + config.slouch_threshold_deg
        torso_threshold = baseline.torso_flexion_baseline + config.forward_lean_threshold_deg
        lateral_threshold = baseline.shoulder_width_proxy * (config.lateral_lean_threshold_cm / 3.0)
        
        # Get detection path and window stats
        detection_path = "none"
        window_stats = {
            "slouch_above_fraction": 0.0,
            "slouch_cumulative_sec": 0.0,
            "slouch_max_gap_sec": 0.0,
            "forward_above_fraction": 0.0,
            "forward_cumulative_sec": 0.0,
            "forward_max_gap_sec": 0.0,
            "lateral_above_fraction": 0.0,
            "lateral_cumulative_sec": 0.0,
            "lateral_max_gap_sec": 0.0
        }
        
        # Get window stats from state machine
        current_time = time.time()
        
        if hasattr(state_machine, 'slouch_window'):
            stats = state_machine.slouch_window.get_stats(current_time, config.slouch_policy.window_sec)
            window_stats["slouch_above_fraction"] = stats["above_fraction"]
            window_stats["slouch_cumulative_sec"] = stats["cumulative_above_sec"]
            window_stats["slouch_max_gap_sec"] = stats["max_gap_sec"]
            
            # Determine detection path for slouch
            if current_state.value == "slouch":
                if stats["above_fraction"] >= config.slouch_policy.majority_fraction:
                    detection_path = "majority"
                elif stats["cumulative_above_sec"] >= config.slouch_policy.cumulative_min_sec:
                    detection_path = "cumulative"
        
        if hasattr(state_machine, 'forward_lean_window'):
            stats = state_machine.forward_lean_window.get_stats(current_time, config.forward_lean_policy.window_sec)
            window_stats["forward_above_fraction"] = stats["above_fraction"]
            window_stats["forward_cumulative_sec"] = stats["cumulative_above_sec"]
            window_stats["forward_max_gap_sec"] = stats["max_gap_sec"]
            
            if current_state.value == "forward_lean":
                if stats["above_fraction"] >= config.forward_lean_policy.majority_fraction:
                    detection_path = "majority"
                elif stats["cumulative_above_sec"] >= config.forward_lean_policy.cumulative_min_sec:
                    detection_path = "cumulative"
        
        if hasattr(state_machine, 'lateral_lean_window'):
            stats = state_machine.lateral_lean_window.get_stats(current_time, config.lateral_lean_policy.window_sec)
            window_stats["lateral_above_fraction"] = stats["above_fraction"]
            window_stats["lateral_cumulative_sec"] = stats["cumulative_above_sec"]
            window_stats["lateral_max_gap_sec"] = stats["max_gap_sec"]
            
            if current_state.value == "lateral_lean":
                if stats["above_fraction"] >= config.lateral_lean_policy.majority_fraction:
                    detection_path = "majority"
                elif stats["cumulative_above_sec"] >= config.lateral_lean_policy.cumulative_min_sec:
                    detection_path = "cumulative"
        
        # Check for high-severity detection
        if hasattr(state_machine, 'last_transition_reason') and state_machine.last_transition_reason:
            if "high-severity" in state_machine.last_transition_reason.lower():
                detection_path = "high_severity"
        
        # Get policy status
        policy_status = policy_engine.get_policy_status()
        
        policy_dict = {
            "cooldown_sec_left": policy_status.get("cooldown_remaining_sec", 0.0),
            "snooze_sec_left": policy_status.get("snooze_remaining_sec", 0.0),
            "backoff_sec_left": policy_status.get("backoff_remaining_sec", 0.0),
            "dnd_queued_count": len(policy_status.get("queued_nudges", [])),
            "last_nudge_age_sec": policy_status.get("last_nudge_sec_ago")
        }
        
        # Create snapshot
        snapshot = StatusSnapshot(
            ts_unix=time.time(),
            state=current_state.value,
            time_in_state_sec=time_in_state,
            confidence=confidence,
            fps=fps,
            metrics={
                "neck_deg": neck_deg,
                "torso_deg": torso_deg,
                "lateral": lateral
            },
            thresholds={
                "neck_abs_deg": neck_threshold,
                "torso_abs_deg": torso_threshold,
                "lateral_abs": lateral_threshold
            },
            preset=preset,
            detection_path=detection_path,
            window_stats=window_stats,
            policy=policy_dict
        )
        
        return snapshot
        
    except Exception as e:
        print(f"[STATUS_BUS] Error creating snapshot: {e}")
        return None
