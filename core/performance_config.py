"""
Performance configuration for CPU optimization.

Defines lightweight defaults and quality mode settings.
PRIVACY: No frames saved, only performance metrics.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PerformanceConfig:
    """
    Performance configuration for pose loop.
    
    Balances CPU usage vs detection quality.
    """
    # FPS settings
    target_fps: float = 6.0  # Default: 6 FPS (lightweight)
    min_fps: float = 4.0  # Governor minimum
    max_fps: float = 8.0  # Governor maximum
    
    # Camera settings
    camera_width: int = 424  # Lightweight: 424×240
    camera_height: int = 240
    
    # MediaPipe settings
    model_complexity: int = 1  # 0=lite, 1=full, 2=heavy (using 1 as default since lite model not always available)
    
    # Frame skip settings
    enable_frame_skip: bool = True
    skip_confidence_threshold: float = 0.75  # Skip when conf ≥ this
    skip_good_state_duration: float = 20.0  # Skip after GOOD for ≥ 20s
    skip_ratio: int = 2  # Process every Nth frame (2 = every other frame)
    
    # Adaptive governor settings
    enable_governor: bool = True
    target_frame_time_ms: float = 120.0  # Target: 120ms per frame
    governor_check_interval: int = 30  # Check every 30 frames
    governor_raise_delay_sec: float = 120.0  # Wait 2 min before raising FPS
    
    # Performance profiling
    enable_profiling: bool = False
    profile_interval_sec: float = 30.0  # Print stats every 30s
    
    @classmethod
    def lightweight(cls) -> 'PerformanceConfig':
        """
        Lightweight preset (default).
        
        Target: < 15% CPU on M-series Mac
        - 6 FPS
        - 424×240 resolution
        - MediaPipe full model (complexity=1)
        - Frame skip enabled
        - Adaptive governor enabled
        """
        return cls(
            target_fps=6.0,
            camera_width=424,
            camera_height=240,
            model_complexity=1,
            enable_frame_skip=True,
            enable_governor=True,
            enable_profiling=False
        )
    
    @classmethod
    def quality(cls) -> 'PerformanceConfig':
        """
        Quality preset (for testing/debugging).
        
        Higher CPU usage but better detection:
        - 8 FPS
        - 640×480 resolution
        - MediaPipe full model (complexity=1)
        - Frame skip disabled
        - Governor disabled
        """
        return cls(
            target_fps=8.0,
            camera_width=640,
            camera_height=480,
            model_complexity=1,
            enable_frame_skip=False,
            enable_governor=False,
            enable_profiling=False
        )
    
    @classmethod
    def performance(cls) -> 'PerformanceConfig':
        """
        Performance preset (ultra-low CPU).
        
        Minimum CPU usage:
        - 4 FPS
        - 320×240 resolution
        - MediaPipe lite model (complexity=0)
        - Frame skip enabled
        - Adaptive governor enabled
        """
        return cls(
            target_fps=4.0,
            camera_width=320,
            camera_height=240,
            model_complexity=0,
            enable_frame_skip=True,
            enable_governor=True,
            enable_profiling=False
        )
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get camera resolution as (width, height)."""
        return (self.camera_width, self.camera_height)
    
    def get_effective_fps(self, skip_active: bool = False) -> float:
        """
        Get effective FPS (accounting for frame skip).
        
        Args:
            skip_active: Whether frame skip is currently active
            
        Returns:
            Effective FPS (compute rate)
        """
        if skip_active and self.enable_frame_skip:
            return self.target_fps / self.skip_ratio
        return self.target_fps
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"PerformanceConfig(fps={self.target_fps}, "
            f"res={self.camera_width}×{self.camera_height}, "
            f"model={'lite' if self.model_complexity == 0 else 'full' if self.model_complexity == 1 else 'heavy'}, "
            f"skip={'on' if self.enable_frame_skip else 'off'}, "
            f"governor={'on' if self.enable_governor else 'off'})"
        )


@dataclass
class PerformanceMetrics:
    """
    Performance metrics for monitoring.
    
    PRIVACY: Only timing metrics, no frames.
    """
    # Frame timing
    frame_count: int = 0
    total_frame_time_ms: float = 0.0
    avg_frame_time_ms: float = 0.0
    min_frame_time_ms: float = float('inf')
    max_frame_time_ms: float = 0.0
    
    # FPS tracking
    actual_fps: float = 0.0
    effective_fps: float = 0.0  # Accounting for frame skip
    
    # Governor state
    governor_level: int = 0  # -2 to +2 (relative to target)
    governor_adjustments: int = 0
    
    # Frame skip state
    frames_skipped: int = 0
    skip_active: bool = False
    
    # CPU estimate (rough)
    cpu_estimate_pct: float = 0.0
    
    def update_frame_time(self, frame_time_ms: float):
        """Update frame timing metrics."""
        self.frame_count += 1
        self.total_frame_time_ms += frame_time_ms
        self.avg_frame_time_ms = self.total_frame_time_ms / self.frame_count
        self.min_frame_time_ms = min(self.min_frame_time_ms, frame_time_ms)
        self.max_frame_time_ms = max(self.max_frame_time_ms, frame_time_ms)
    
    def estimate_cpu(self, target_fps: float):
        """
        Estimate CPU usage based on frame time.
        
        Rough estimate: (frame_time_ms / 1000) * target_fps * 100
        """
        if self.avg_frame_time_ms > 0:
            self.cpu_estimate_pct = (self.avg_frame_time_ms / 1000.0) * target_fps * 100.0
    
    def reset(self):
        """Reset metrics for new profiling window."""
        self.frame_count = 0
        self.total_frame_time_ms = 0.0
        self.avg_frame_time_ms = 0.0
        self.min_frame_time_ms = float('inf')
        self.max_frame_time_ms = 0.0
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"FPS={self.actual_fps:.1f} (effective={self.effective_fps:.1f}), "
            f"CPU est={self.cpu_estimate_pct:.1f}%, "
            f"governor={self.governor_level:+d}, "
            f"skip={'on' if self.skip_active else 'off'}, "
            f"avg_ms={self.avg_frame_time_ms:.1f}"
        )
