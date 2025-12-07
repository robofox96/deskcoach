"""
Background pose monitoring loop.
Captures webcam frames, runs pose estimation, computes metrics, and maintains state.

PRIVACY: Never writes frames to disk. Only metrics are computed and stored.
"""

import time
import threading
from typing import Optional, Dict, Any, Callable
import cv2
import mediapipe as mp
from .platform import is_macos
from .metrics import (
    MetricsCalculator, 
    EMASmoothing, 
    RollingBuffer, 
    PostureMetrics, 
    PostureState
)
from .state_machine import PostureStateMachine, StateTransitionEvent
from .storage import CalibrationBaseline
from .performance_config import PerformanceConfig, PerformanceMetrics


class PoseLoop:
    """
    Background service for continuous pose monitoring.
    
    Privacy guarantee: Never saves frames. Only computes and stores metrics.
    """
    
    def __init__(
        self,
        camera_index: int = 0,
        target_fps: float = 6.0,
        ema_alpha: float = 0.3,
        window_seconds: float = 60.0,
        baseline: Optional[CalibrationBaseline] = None,
        state_transition_callback: Optional[Callable[[StateTransitionEvent], None]] = None,
        perf_config: Optional[PerformanceConfig] = None
    ):
        """
        Initialize pose monitoring loop.
        
        Args:
            camera_index: Webcam device index (default 0)
            target_fps: Target frame rate (5-10 recommended)
            ema_alpha: EMA smoothing factor (0.3 = moderate smoothing)
            window_seconds: Rolling window for sustained detection (60s default)
            baseline: Calibration baseline (optional, for state machine)
            state_transition_callback: Callback for state transitions (optional)
        """
        self.camera_index = camera_index
        self.perf_config = perf_config or PerformanceConfig.lightweight()
        self.target_fps = target_fps if target_fps != 6.0 else self.perf_config.target_fps
        self.frame_interval = 1.0 / self.target_fps
        self.state_transition_callback = state_transition_callback
        
        # Performance tracking
        self.perf_metrics = PerformanceMetrics()
        self.frame_times = []  # For governor
        self.governor_last_adjust = time.time()
        self.frame_skip_counter = 0
        self.good_state_start_time: Optional[float] = None
        self.last_profile_time = time.time()
        
        # MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = None
        
        # Metrics computation
        self.metrics_calc = MetricsCalculator()
        
        # Smoothing and buffering
        self.neck_ema = EMASmoothing(alpha=ema_alpha)
        self.torso_ema = EMASmoothing(alpha=ema_alpha)
        self.lateral_ema = EMASmoothing(alpha=ema_alpha)
        
        self.neck_buffer = RollingBuffer(window_seconds=window_seconds)
        self.torso_buffer = RollingBuffer(window_seconds=window_seconds)
        self.lateral_buffer = RollingBuffer(window_seconds=window_seconds)
        
        # State
        self.running = False
        self.paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Latest metrics
        self._latest_metrics: Optional[PostureMetrics] = None
        self._current_state = PostureState.PAUSED
        
        # State machine (if baseline provided)
        self.state_machine: Optional[PostureStateMachine] = None
        if baseline:
            self.state_machine = PostureStateMachine(baseline)
        
        # Stats
        self.frames_processed = 0
        self.start_time: Optional[float] = None
        self.last_frame_time: Optional[float] = None
        
        # Camera
        self.cap: Optional[cv2.VideoCapture] = None
    
    def start(self):
        """Start the pose monitoring loop in a background thread."""
        if self.running:
            return
        
        self.running = True
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the pose monitoring loop and release resources."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._cleanup()
    
    def pause(self):
        """Pause pose evaluation (camera still runs but no processing)."""
        with self._lock:
            self.paused = True
            self._current_state = PostureState.PAUSED
    
    def resume(self):
        """Resume pose evaluation."""
        with self._lock:
            self.paused = False
    
    def get_latest_metrics(self) -> Optional[PostureMetrics]:
        """Get the most recent computed metrics (thread-safe)."""
        with self._lock:
            return self._latest_metrics
    
    def get_current_state(self) -> PostureState:
        """Get the current posture state."""
        with self._lock:
            return self._current_state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get runtime statistics."""
        with self._lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            actual_fps = self.frames_processed / elapsed if elapsed > 0 else 0
            
            stats = {
                "frames_processed": self.frames_processed,
                "elapsed_seconds": elapsed,
                "actual_fps": actual_fps,
                "target_fps": self.target_fps,
                "state": self._current_state.value,
                "paused": self.paused,
                "neck_buffer_size": self.neck_buffer.size(),
                "torso_buffer_size": self.torso_buffer.size(),
                "lateral_buffer_size": self.lateral_buffer.size()
            }
            
            # Add state machine stats if available
            if self.state_machine:
                stats["state_machine"] = self.state_machine.get_state_summary()
                stats["state_counts"] = self.state_machine.get_state_counts()
            
            return stats
    
    def get_state_machine(self) -> Optional[PostureStateMachine]:
        """Get the state machine instance (if available)."""
        return self.state_machine
    
    def _run_loop(self):
        """Main processing loop (runs in background thread)."""
        # Initialize camera
        if not self._init_camera():
            print("ERROR: Failed to initialize camera")
            self.running = False
            return
        
        # Initialize MediaPipe Pose with performance config
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=self.perf_config.model_complexity,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        print(f"Pose loop started (target {self.target_fps} FPS)")
        
        try:
            while self.running:
                loop_start = time.time()
                
                # Process one frame
                frame_time_ms = self._process_frame()
                
                # Update performance metrics
                if frame_time_ms is not None:
                    self.perf_metrics.update_frame_time(frame_time_ms)
                    self.frame_times.append(frame_time_ms)
                    
                    # Adaptive governor check
                    if self.perf_config.enable_governor and len(self.frame_times) >= self.perf_config.governor_check_interval:
                        self._check_governor()
                    
                    # Performance profiling
                    if self.perf_config.enable_profiling:
                        self._check_profiling()
                
                # FPS governor: sleep to maintain target FPS
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        finally:
            self._cleanup()
    
    def _init_camera(self) -> bool:
        """Initialize camera capture."""
        try:
            # On macOS, OpenCV needs camera permission
            # Set environment variable to skip auth in thread (must be done in main)
            import os
            if is_macos():
                os.environ.setdefault('OPENCV_AVFOUNDATION_SKIP_AUTH', '1')
            
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                if is_macos():
                    print("ERROR: Camera not accessible. Please grant camera permission:")
                    print("  System Settings → Privacy & Security → Camera → Terminal (or your IDE)")
                else:
                    print("ERROR: Camera not accessible. Check that no other application is using it and that OS camera permissions are granted.")
                return False
            
            # Set camera properties from performance config
            width, height = self.perf_config.get_resolution()
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            
            # Test read
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print("ERROR: Camera opened but cannot read frames. Check permissions.")
                return False
            
            return True
        except Exception as e:
            print(f"Camera init error: {e}")
            return False
    
    def _check_governor(self):
        """Adaptive FPS governor - adjust target FPS based on frame time."""
        if not self.frame_times:
            return
        
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        self.frame_times.clear()
        
        current_time = time.time()
        
        # Check if frame time exceeds target
        if avg_frame_time > self.perf_config.target_frame_time_ms:
            # Drop FPS if above minimum
            if self.target_fps > self.perf_config.min_fps:
                self.target_fps -= 1.0
                self.frame_interval = 1.0 / self.target_fps
                self.perf_metrics.governor_level -= 1
                self.perf_metrics.governor_adjustments += 1
                self.governor_last_adjust = current_time
                print(f"[GOVERNOR] Frame time {avg_frame_time:.1f}ms > target {self.perf_config.target_frame_time_ms:.1f}ms, dropping to {self.target_fps:.1f} FPS")
        
        # Check if we can raise FPS (under budget for 2 minutes)
        elif avg_frame_time < self.perf_config.target_frame_time_ms * 0.7:
            time_since_adjust = current_time - self.governor_last_adjust
            if time_since_adjust >= self.perf_config.governor_raise_delay_sec:
                if self.target_fps < self.perf_config.max_fps:
                    self.target_fps += 1.0
                    self.frame_interval = 1.0 / self.target_fps
                    self.perf_metrics.governor_level += 1
                    self.perf_metrics.governor_adjustments += 1
                    self.governor_last_adjust = current_time
                    print(f"[GOVERNOR] Frame time {avg_frame_time:.1f}ms < target, raising to {self.target_fps:.1f} FPS")
    
    def _check_profiling(self):
        """Print performance profile if interval elapsed."""
        current_time = time.time()
        if current_time - self.last_profile_time >= self.perf_config.profile_interval_sec:
            self.last_profile_time = current_time
            
            # Update metrics
            elapsed = current_time - self.start_time if self.start_time else 0
            self.perf_metrics.actual_fps = self.frames_processed / elapsed if elapsed > 0 else 0
            self.perf_metrics.effective_fps = self.perf_config.get_effective_fps(self.perf_metrics.skip_active)
            self.perf_metrics.estimate_cpu(self.target_fps)
            
            # Print profile
            width, height = self.perf_config.get_resolution()
            model_name = 'lite' if self.perf_config.model_complexity == 0 else 'full' if self.perf_config.model_complexity == 1 else 'heavy'
            
            print(f"[PERF] {self.perf_metrics}, res={width}×{height}, model={model_name}")
    
    def _should_skip_frame(self, metrics: Optional[PostureMetrics]) -> bool:
        """
        Determine if frame should be skipped based on frame skip policy.
        
        Skip when:
        - Frame skip enabled
        - Confidence >= threshold
        - State = GOOD for >= duration
        - Skip counter indicates skip
        """
        if not self.perf_config.enable_frame_skip:
            return False
        
        if not metrics:
            return False
        
        # Check confidence
        if metrics.confidence < self.perf_config.skip_confidence_threshold:
            self.good_state_start_time = None
            self.perf_metrics.skip_active = False
            return False
        
        # Check state
        if metrics.state != PostureState.GOOD:
            self.good_state_start_time = None
            self.perf_metrics.skip_active = False
            return False
        
        # Track GOOD state duration
        current_time = time.time()
        if self.good_state_start_time is None:
            self.good_state_start_time = current_time
            self.perf_metrics.skip_active = False
            return False
        
        time_in_good = current_time - self.good_state_start_time
        if time_in_good < self.perf_config.skip_good_state_duration:
            self.perf_metrics.skip_active = False
            return False
        
        # Conditions met - check skip counter
        self.perf_metrics.skip_active = True
        self.frame_skip_counter += 1
        
        if self.frame_skip_counter % self.perf_config.skip_ratio == 0:
            # Process this frame
            return False
        else:
            # Skip this frame
            self.perf_metrics.frames_skipped += 1
            return True
    
    def _process_frame(self) -> Optional[float]:
        """
        Process a single frame: capture, pose estimation, metrics computation.
        
        PRIVACY: Frame is never saved. Only metrics are computed and stored.
        
        Returns:
            Frame processing time in milliseconds, or None if skipped/error
        """
        frame_start = time.time()
        if not self.cap or not self.cap.isOpened():
            # Try to recover
            if not self._init_camera():
                time.sleep(1.0)  # Wait before retry
                return
        
        # Capture frame
        ret, frame = self.cap.read()
        if not ret or frame is None:
            # Camera error - pause state
            with self._lock:
                self._current_state = PostureState.PAUSED
            return None
        
        # PRIVACY: Frame is only in memory here, never written to disk
        
        # Check if paused
        if self.paused:
            # Frame captured but not processed
            return None
        
        # Check if we should skip this frame (for performance)
        # Note: We need previous metrics to decide, so check after first frame
        if self.frames_processed > 0 and self._should_skip_frame(self._latest_metrics):
            # Skip processing but maintain StatusBus rate
            return None
        
        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Run pose estimation
        results = self.pose.process(frame_rgb)
        
        # PRIVACY: frame and frame_rgb go out of scope here and are garbage collected
        # No frames are retained beyond this point
        
        timestamp = time.time()
        self.frames_processed += 1
        self.last_frame_time = timestamp
        
        # Compute metrics
        if results.pose_landmarks:
            metrics = self.metrics_calc.compute_metrics(results.pose_landmarks, timestamp)
            
            if metrics:
                # Apply EMA smoothing
                smoothed_neck = self.neck_ema.update(metrics.neck_flexion)
                smoothed_torso = self.torso_ema.update(metrics.torso_flexion)
                smoothed_lateral = self.lateral_ema.update(metrics.lateral_lean)
                
                # Update rolling buffers
                self.neck_buffer.add(timestamp, smoothed_neck)
                self.torso_buffer.add(timestamp, smoothed_torso)
                self.lateral_buffer.add(timestamp, smoothed_lateral)
                
                # Update metrics with smoothed values
                metrics.neck_flexion = smoothed_neck
                metrics.torso_flexion = smoothed_torso
                metrics.lateral_lean = smoothed_lateral
                
                # Update state machine if available
                if self.state_machine:
                    event = self.state_machine.update(metrics)
                    
                    # Get state from state machine
                    metrics.state = self.state_machine.get_current_state()
                    
                    # Emit event if state changed
                    if event and self.state_transition_callback:
                        self.state_transition_callback(event)
                else:
                    # No state machine - simple GOOD/PAUSED logic
                    if metrics.confidence < MetricsCalculator.MIN_CONFIDENCE:
                        metrics.state = PostureState.PAUSED
                    else:
                        metrics.state = PostureState.GOOD
                
                # Store latest metrics
                with self._lock:
                    self._latest_metrics = metrics
                    self._current_state = metrics.state
        else:
            # No pose detected - paused state
            with self._lock:
                self._current_state = PostureState.PAUSED
        
        # Return frame processing time
        frame_time_ms = (time.time() - frame_start) * 1000.0
        return frame_time_ms
    
    def _cleanup(self):
        """Release camera and MediaPipe resources."""
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if self.pose:
            self.pose.close()
            self.pose = None
        
        print("Pose loop stopped")
