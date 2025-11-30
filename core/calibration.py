"""
Calibration routine for capturing neutral posture baseline.

Captures 20-30 seconds of pose data while user sits upright,
computes median metrics, and persists baselines.

PRIVACY: Never saves frames, only computed metrics.
"""

import time
from typing import Optional, List, Callable
from datetime import datetime
from .pose_loop import PoseLoop
from .metrics import PostureMetrics
from .storage import CalibrationBaseline, CalibrationStorage


class CalibrationRoutine:
    """
    Manages calibration process for capturing neutral posture baseline.
    
    Privacy: Only metrics are captured and stored, never frames.
    """
    
    def __init__(
        self,
        pose_loop: PoseLoop,
        storage: Optional[CalibrationStorage] = None,
        duration_seconds: float = 25.0
    ):
        """
        Initialize calibration routine.
        
        Args:
            pose_loop: Active pose loop instance
            storage: Storage instance (creates default if None)
            duration_seconds: Calibration capture duration (20-30s recommended)
        """
        self.pose_loop = pose_loop
        self.storage = storage or CalibrationStorage()
        self.duration_seconds = duration_seconds
        
        # Calibration state
        self.is_calibrating = False
        self.captured_metrics: List[PostureMetrics] = []
        self.start_time: Optional[float] = None
    
    def run_calibration(
        self,
        progress_callback: Optional[Callable] = None
    ) -> Optional[CalibrationBaseline]:
        """
        Run calibration routine.
        
        Captures metrics for the specified duration, computes medians,
        and saves baseline to storage.
        
        Args:
            progress_callback: Optional callback for progress updates.
                Can be simple callback(elapsed_seconds, sample_count)
                or rich callback from CalibrationProgressCallback.update()
            
        Returns:
            CalibrationBaseline if successful, None otherwise
        """
        if self.is_calibrating:
            print("ERROR: Calibration already in progress")
            return None
        
        if not self.pose_loop.running:
            print("ERROR: Pose loop must be running before calibration")
            return None
        
        print("=" * 80)
        print("CALIBRATION ROUTINE")
        print("=" * 80)
        print(f"Duration: {self.duration_seconds}s")
        print()
        print("Instructions:")
        print("  1. Sit comfortably upright in your natural good posture")
        print("  2. Look straight ahead at the camera")
        print("  3. Keep shoulders level and relaxed")
        print("  4. Stay still for the next ~25 seconds")
        print()
        print("Starting in 3 seconds...")
        print()
        
        # Notify preparing phase
        if progress_callback:
            try:
                progress_callback(phase="preparing", samples_captured=0, conf_mean=0.0)
            except TypeError:
                # Simple callback, ignore
                pass
        
        time.sleep(3)
        
        # Start capture
        self.is_calibrating = True
        self.captured_metrics = []
        self.start_time = time.time()
        
        print("Capturing baseline... (stay still)")
        
        try:
            while True:
                elapsed = time.time() - self.start_time
                
                if elapsed >= self.duration_seconds:
                    break
                
                # Get latest metrics
                metrics = self.pose_loop.get_latest_metrics()
                
                if metrics and metrics.confidence >= 0.5:
                    self.captured_metrics.append(metrics)
                
                # Progress callback
                if progress_callback:
                    conf_mean = sum(m.confidence for m in self.captured_metrics) / len(self.captured_metrics) if self.captured_metrics else 0.0
                    try:
                        # Try rich callback first
                        progress_callback(
                            phase="capturing",
                            samples_captured=len(self.captured_metrics),
                            conf_mean=conf_mean
                        )
                    except TypeError:
                        # Fall back to simple callback
                        try:
                            progress_callback(elapsed, len(self.captured_metrics))
                        except:
                            pass
                
                time.sleep(0.1)  # Check every 100ms
            
            # Notify aggregating phase
            if progress_callback:
                try:
                    conf_mean = sum(m.confidence for m in self.captured_metrics) / len(self.captured_metrics) if self.captured_metrics else 0.0
                    progress_callback(
                        phase="aggregating",
                        samples_captured=len(self.captured_metrics),
                        conf_mean=conf_mean
                    )
                except TypeError:
                    pass
            
            # Compute baseline
            baseline = self._compute_baseline()
            
            if baseline is None:
                print()
                print("ERROR: Failed to compute baseline (insufficient data)")
                if progress_callback:
                    try:
                        progress_callback(
                            phase="error",
                            samples_captured=len(self.captured_metrics),
                            conf_mean=0.0,
                            error_message="Insufficient data captured"
                        )
                    except TypeError:
                        pass
                return None
            
            # Notify saving phase
            if progress_callback:
                try:
                    progress_callback(
                        phase="saving",
                        samples_captured=baseline.sample_count,
                        conf_mean=baseline.confidence_mean
                    )
                except TypeError:
                    pass
            
            # Save baseline
            success = self.storage.save_baseline(baseline)
            
            if not success:
                print()
                print("ERROR: Failed to save baseline to storage")
                if progress_callback:
                    try:
                        progress_callback(
                            phase="error",
                            samples_captured=baseline.sample_count,
                            conf_mean=baseline.confidence_mean,
                            error_message="Failed to save baseline to storage"
                        )
                    except TypeError:
                        pass
                return None
            
            print()
            print("=" * 80)
            print("CALIBRATION COMPLETE")
            print("=" * 80)
            print(f"Samples captured: {baseline.sample_count}")
            print(f"Average confidence: {baseline.confidence_mean:.2f}")
            print()
            print("Baseline values:")
            print(f"  Neck flexion:    {baseline.neck_flexion_baseline:6.2f}°")
            print(f"  Torso flexion:   {baseline.torso_flexion_baseline:6.2f}°")
            print(f"  Lateral lean:    {baseline.lateral_lean_baseline:6.3f}")
            print(f"  Shoulder width:  {baseline.shoulder_width_proxy:6.3f}")
            print()
            print("Baseline saved successfully!")
            print("=" * 80)
            
            # Notify done phase
            if progress_callback:
                try:
                    progress_callback(
                        phase="done",
                        samples_captured=baseline.sample_count,
                        conf_mean=baseline.confidence_mean,
                        baseline_values={
                            "neck_flexion_baseline": baseline.neck_flexion_baseline,
                            "torso_flexion_baseline": baseline.torso_flexion_baseline,
                            "lateral_lean_baseline": baseline.lateral_lean_baseline,
                            "shoulder_width_proxy": baseline.shoulder_width_proxy
                        }
                    )
                except TypeError:
                    pass
            
            return baseline
            
        finally:
            self.is_calibrating = False
            self.captured_metrics = []
            self.start_time = None
    
    def _compute_baseline(self) -> Optional[CalibrationBaseline]:
        """
        Compute baseline from captured metrics.
        
        Uses median for robustness to outliers.
        
        Returns:
            CalibrationBaseline if sufficient data, None otherwise
        """
        if len(self.captured_metrics) < 50:  # Need at least ~5s of data at 10 FPS
            return None
        
        # Extract metric arrays
        neck_values = [m.neck_flexion for m in self.captured_metrics]
        torso_values = [m.torso_flexion for m in self.captured_metrics]
        lateral_values = [m.lateral_lean for m in self.captured_metrics]
        confidence_values = [m.confidence for m in self.captured_metrics]
        
        # Compute medians
        neck_baseline = self._median(neck_values)
        torso_baseline = self._median(torso_values)
        lateral_baseline = self._median(lateral_values)
        confidence_mean = sum(confidence_values) / len(confidence_values)
        
        # Compute shoulder width proxy
        # Use the median lateral lean as a scale reference
        # In neutral posture, this represents the natural asymmetry
        shoulder_width_proxy = lateral_baseline
        
        # Create baseline object
        baseline = CalibrationBaseline(
            neck_flexion_baseline=neck_baseline,
            torso_flexion_baseline=torso_baseline,
            lateral_lean_baseline=lateral_baseline,
            shoulder_width_proxy=shoulder_width_proxy,
            calibrated_at=datetime.now().isoformat(),
            sample_count=len(self.captured_metrics),
            confidence_mean=confidence_mean
        )
        
        return baseline
    
    def _median(self, values: List[float]) -> float:
        """Compute median of a list of values."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if n == 0:
            return 0.0
        
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def get_progress(self) -> Optional[dict]:
        """
        Get current calibration progress.
        
        Returns:
            Dictionary with progress info if calibrating, None otherwise
        """
        if not self.is_calibrating or self.start_time is None:
            return None
        
        elapsed = time.time() - self.start_time
        remaining = max(0, self.duration_seconds - elapsed)
        progress_pct = min(100, (elapsed / self.duration_seconds) * 100)
        
        return {
            "elapsed": elapsed,
            "remaining": remaining,
            "progress_pct": progress_pct,
            "samples": len(self.captured_metrics)
        }
