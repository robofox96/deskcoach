"""
Calibration Status - Progress tracking for UI.

Publishes calibration progress to storage/calibration_status.json at ~4 Hz.
PRIVACY: No frames saved, only progress metrics.
"""

import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from enum import Enum


class CalibrationPhase(Enum):
    """Calibration phases."""
    IDLE = "idle"
    PREPARING = "preparing"
    CAPTURING = "capturing"
    AGGREGATING = "aggregating"
    SAVING = "saving"
    DONE = "done"
    ERROR = "error"


@dataclass
class CalibrationProgress:
    """
    Calibration progress snapshot.
    
    PRIVACY: Contains only progress metrics, no frames.
    """
    # Phase
    phase: str  # idle, preparing, capturing, aggregating, saving, done, error
    
    # Progress
    progress_0_1: float  # 0.0 to 1.0
    elapsed_sec: float
    
    # Capture stats
    samples_captured: int
    conf_mean: float
    
    # Timing
    eta_sec: Optional[float] = None
    
    # Final results (only on done)
    baseline_neck: Optional[float] = None
    baseline_torso: Optional[float] = None
    baseline_lateral: Optional[float] = None
    baseline_shoulder_width: Optional[float] = None
    
    # Error info (only on error)
    error_message: Optional[str] = None


class CalibrationStatusPublisher:
    """
    Publishes calibration progress to JSON file.
    
    Thread-safe, atomic writes, ~4 Hz update rate.
    """
    
    def __init__(
        self,
        status_file: str = "storage/calibration_status.json",
        update_interval_sec: float = 0.25  # 4 Hz
    ):
        """
        Initialize status publisher.
        
        Args:
            status_file: Path to status JSON file
            update_interval_sec: Minimum time between updates (default: 0.25s = 4 Hz)
        """
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.update_interval_sec = update_interval_sec
        self._last_update_time = 0.0
    
    def publish(self, progress: CalibrationProgress, force: bool = False):
        """
        Publish calibration progress.
        
        Rate-limited to ~4 Hz unless force=True.
        
        Args:
            progress: CalibrationProgress to publish
            force: Force immediate publish (ignore rate limit)
        """
        current_time = time.time()
        
        # Rate limiting (unless forced)
        if not force:
            if current_time - self._last_update_time < self.update_interval_sec:
                return
        
        self._last_update_time = current_time
        
        try:
            # Convert to dict
            data = asdict(progress)
            
            # Serialize to JSON
            json_str = json.dumps(data, indent=2)
            
            # Atomic write
            temp_file = self.status_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(json_str)
            os.replace(temp_file, self.status_file)
            
        except Exception as e:
            print(f"[CALIBRATION_STATUS] Error publishing: {e}")
    
    def clear(self):
        """Clear the status file."""
        try:
            if self.status_file.exists():
                self.status_file.unlink()
        except Exception:
            pass


def read_calibration_status(
    status_file: str = "storage/calibration_status.json"
) -> Optional[CalibrationProgress]:
    """
    Read calibration status from file.
    
    Args:
        status_file: Path to status JSON file
        
    Returns:
        CalibrationProgress or None if not available
    """
    status_path = Path(status_file)
    
    if not status_path.exists():
        return None
    
    try:
        with open(status_path, 'r') as f:
            data = json.load(f)
        
        return CalibrationProgress(**data)
    except Exception:
        return None


class CalibrationProgressCallback:
    """
    Callback for calibration progress updates.
    
    Usage:
        callback = CalibrationProgressCallback()
        routine = CalibrationRoutine(..., progress_callback=callback.update)
    """
    
    def __init__(self):
        self.publisher = CalibrationStatusPublisher()
        self.start_time = time.time()
        self.duration_sec = 25.0  # Default, will be updated
    
    def update(
        self,
        phase: str,
        samples_captured: int = 0,
        conf_mean: float = 0.0,
        baseline_values: Optional[Dict[str, float]] = None,
        error_message: Optional[str] = None
    ):
        """
        Update calibration progress.
        
        Args:
            phase: Current phase (preparing, capturing, etc.)
            samples_captured: Number of samples captured so far
            conf_mean: Mean confidence of captured samples
            baseline_values: Final baseline values (on done)
            error_message: Error message (on error)
        """
        elapsed = time.time() - self.start_time
        
        # Calculate progress
        if phase == "preparing":
            progress = 0.0
            eta = self.duration_sec
        elif phase == "capturing":
            # Progress based on samples (assume ~8 FPS * duration)
            expected_samples = 8.0 * self.duration_sec
            progress = min(0.9, samples_captured / expected_samples) if expected_samples > 0 else 0.0
            remaining = max(0, self.duration_sec - elapsed)
            eta = remaining
        elif phase == "aggregating":
            progress = 0.95
            eta = 1.0
        elif phase == "saving":
            progress = 0.98
            eta = 0.5
        elif phase == "done":
            progress = 1.0
            eta = 0.0
        elif phase == "error":
            progress = 0.0
            eta = None
        else:
            progress = 0.0
            eta = None
        
        # Build progress object
        prog = CalibrationProgress(
            phase=phase,
            progress_0_1=progress,
            elapsed_sec=elapsed,
            samples_captured=samples_captured,
            conf_mean=conf_mean,
            eta_sec=eta,
            error_message=error_message
        )
        
        # Add baseline values if done
        if baseline_values:
            prog.baseline_neck = baseline_values.get("neck_flexion_baseline")
            prog.baseline_torso = baseline_values.get("torso_flexion_baseline")
            prog.baseline_lateral = baseline_values.get("lateral_lean_baseline")
            prog.baseline_shoulder_width = baseline_values.get("shoulder_width_proxy")
        
        # Publish (force on phase changes)
        force = phase in ["preparing", "done", "error"]
        self.publisher.publish(prog, force=force)
    
    def set_duration(self, duration_sec: float):
        """Set expected calibration duration."""
        self.duration_sec = duration_sec
