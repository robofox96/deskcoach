"""
Posture metrics computation using MediaPipe landmarks.
Implements neck flexion, torso flexion, and lateral lean calculations.
"""

import math
from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass
import numpy as np


class PostureState(Enum):
    """Posture evaluation states."""
    GOOD = "good"
    SLOUCH = "slouch"
    FORWARD_LEAN = "forward_lean"
    LATERAL_LEAN = "lateral_lean"
    PAUSED = "paused"


@dataclass
class PostureMetrics:
    """Container for computed posture metrics."""
    neck_flexion: float  # degrees
    torso_flexion: float  # degrees
    lateral_lean: float  # shoulder height difference (normalized)
    confidence: float  # average landmark confidence
    timestamp: float
    state: PostureState = PostureState.GOOD


class MetricsCalculator:
    """
    Computes posture metrics from MediaPipe Pose landmarks.
    Uses relative vectors to be robust to camera tilt.
    
    Privacy: Never stores frames, only computed angles.
    """
    
    # MediaPipe Pose landmark indices
    NOSE = 0
    LEFT_EYE = 2
    RIGHT_EYE = 5
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    
    # Confidence threshold for reliable detection
    MIN_CONFIDENCE = 0.5
    
    def __init__(self):
        """Initialize metrics calculator."""
        pass
    
    def compute_metrics(self, landmarks, timestamp: float) -> Optional[PostureMetrics]:
        """
        Compute posture metrics from pose landmarks.
        
        Args:
            landmarks: MediaPipe pose landmarks (33 points)
            timestamp: Current timestamp
            
        Returns:
            PostureMetrics if confidence is sufficient, None otherwise
        """
        if landmarks is None:
            return None
        
        # Extract key landmarks
        try:
            left_ear = self._get_landmark(landmarks, self.LEFT_EAR)
            right_ear = self._get_landmark(landmarks, self.RIGHT_EAR)
            left_shoulder = self._get_landmark(landmarks, self.LEFT_SHOULDER)
            right_shoulder = self._get_landmark(landmarks, self.RIGHT_SHOULDER)
            left_hip = self._get_landmark(landmarks, self.LEFT_HIP)
            right_hip = self._get_landmark(landmarks, self.RIGHT_HIP)
            
            # Check confidence
            avg_confidence = self._compute_average_confidence([
                left_ear, right_ear, left_shoulder, right_shoulder, left_hip, right_hip
            ])
            
            if avg_confidence < self.MIN_CONFIDENCE:
                return PostureMetrics(
                    neck_flexion=0.0,
                    torso_flexion=0.0,
                    lateral_lean=0.0,
                    confidence=avg_confidence,
                    timestamp=timestamp,
                    state=PostureState.PAUSED
                )
            
            # Compute midpoints
            ear_mid = self._midpoint(left_ear, right_ear)
            shoulder_mid = self._midpoint(left_shoulder, right_shoulder)
            hip_mid = self._midpoint(left_hip, right_hip)
            
            # Compute metrics
            neck_flexion = self._compute_neck_flexion(ear_mid, shoulder_mid)
            torso_flexion = self._compute_torso_flexion(shoulder_mid, hip_mid)
            lateral_lean = self._compute_lateral_lean(left_shoulder, right_shoulder, left_ear, right_ear)
            
            return PostureMetrics(
                neck_flexion=neck_flexion,
                torso_flexion=torso_flexion,
                lateral_lean=lateral_lean,
                confidence=avg_confidence,
                timestamp=timestamp,
                state=PostureState.GOOD
            )
            
        except (IndexError, AttributeError, TypeError) as e:
            # Landmarks not available or malformed
            return None
    
    def _get_landmark(self, landmarks, index: int) -> Tuple[float, float, float]:
        """Extract (x, y, visibility) from landmark."""
        lm = landmarks.landmark[index]
        return (lm.x, lm.y, lm.visibility)
    
    def _compute_average_confidence(self, landmarks: list) -> float:
        """Compute average visibility/confidence across landmarks."""
        if not landmarks:
            return 0.0
        confidences = [lm[2] for lm in landmarks if len(lm) > 2]
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _midpoint(self, p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> Tuple[float, float]:
        """Compute midpoint between two landmarks (x, y only)."""
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    
    def _compute_neck_flexion(self, ear_mid: Tuple[float, float], shoulder_mid: Tuple[float, float]) -> float:
        """
        Compute neck flexion angle: angle between shoulder→ear vector and vertical.
        Positive angle = forward head posture.
        """
        # Vector from shoulder to ear
        dx = ear_mid[0] - shoulder_mid[0]
        dy = ear_mid[1] - shoulder_mid[1]  # Note: y increases downward in image coords
        
        # Angle from vertical (in image coords, vertical is dy direction)
        # We want the horizontal deviation
        angle_rad = math.atan2(abs(dx), abs(dy))
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
    
    def _compute_torso_flexion(self, shoulder_mid: Tuple[float, float], hip_mid: Tuple[float, float]) -> float:
        """
        Compute torso flexion angle: angle between hip→shoulder vector and vertical.
        Positive angle = leaning forward.
        """
        dx = shoulder_mid[0] - hip_mid[0]
        dy = shoulder_mid[1] - hip_mid[1]  # y increases downward
        
        angle_rad = math.atan2(abs(dx), abs(dy))
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
    
    def _compute_lateral_lean(
        self, 
        left_shoulder: Tuple[float, float, float], 
        right_shoulder: Tuple[float, float, float],
        left_ear: Tuple[float, float, float],
        right_ear: Tuple[float, float, float]
    ) -> float:
        """
        Compute lateral lean: shoulder height difference normalized by shoulder width.
        Returns a scale-independent measure of asymmetry.
        """
        # Shoulder height difference (y-coordinate difference)
        shoulder_height_diff = abs(left_shoulder[1] - right_shoulder[1])
        
        # Shoulder width for normalization
        shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
        
        # Avoid division by zero
        if shoulder_width < 0.01:
            return 0.0
        
        # Normalized lateral lean (dimensionless ratio)
        lateral_ratio = shoulder_height_diff / shoulder_width
        
        return lateral_ratio


class EMASmoothing:
    """
    Exponential Moving Average smoothing for metrics.
    Reduces jitter while maintaining responsiveness.
    """
    
    def __init__(self, alpha: float = 0.3):
        """
        Initialize EMA smoother.
        
        Args:
            alpha: Smoothing factor (0-1). Higher = more responsive, lower = smoother.
        """
        self.alpha = alpha
        self.value: Optional[float] = None
    
    def update(self, new_value: float) -> float:
        """Update EMA with new value and return smoothed result."""
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value
    
    def get(self) -> Optional[float]:
        """Get current smoothed value."""
        return self.value
    
    def reset(self):
        """Reset the smoother."""
        self.value = None


class RollingBuffer:
    """
    Rolling buffer for maintaining a time window of metrics.
    Used for sustained-condition detection.
    """
    
    def __init__(self, window_seconds: float = 60.0):
        """
        Initialize rolling buffer.
        
        Args:
            window_seconds: Time window to maintain (seconds)
        """
        self.window_seconds = window_seconds
        self.buffer = []  # List of (timestamp, value) tuples
    
    def add(self, timestamp: float, value: float):
        """Add a new value to the buffer."""
        self.buffer.append((timestamp, value))
        self._prune(timestamp)
    
    def _prune(self, current_time: float):
        """Remove entries older than the window."""
        cutoff = current_time - self.window_seconds
        self.buffer = [(t, v) for t, v in self.buffer if t >= cutoff]
    
    def get_values(self) -> list:
        """Get all values in the current window."""
        return [v for _, v in self.buffer]
    
    def get_mean(self) -> Optional[float]:
        """Get mean of values in the window."""
        values = self.get_values()
        return sum(values) / len(values) if values else None
    
    def get_median(self) -> Optional[float]:
        """Get median of values in the window."""
        values = self.get_values()
        if not values:
            return None
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def size(self) -> int:
        """Get number of entries in the buffer."""
        return len(self.buffer)
    
    def clear(self):
        """Clear the buffer."""
        self.buffer = []
