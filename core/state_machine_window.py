"""
Rolling window for tracking sustained conditions.
"""

from typing import List, Tuple, Dict, Any


class ConditionWindow:
    """
    Rolling window for tracking condition over time.
    
    Tracks (timestamp, above_threshold) samples and computes statistics:
    - above_fraction: Percentage of samples above threshold
    - cumulative_above_sec: Total time spent above threshold
    - max_gap_sec: Longest continuous gap below threshold
    """
    
    def __init__(self):
        """Initialize empty window."""
        self.samples: List[Tuple[float, bool]] = []
    
    def add(self, timestamp: float, above_threshold: bool):
        """
        Add a sample to the window.
        
        Args:
            timestamp: Unix timestamp
            above_threshold: Whether metric exceeds threshold
        """
        self.samples.append((timestamp, above_threshold))
    
    def trim(self, window_sec: float, current_time: float):
        """
        Remove samples older than window_sec.
        
        Args:
            window_sec: Window duration in seconds
            current_time: Current timestamp
        """
        cutoff = current_time - window_sec
        self.samples = [(t, v) for t, v in self.samples if t >= cutoff]
    
    def clear(self):
        """Clear all samples."""
        self.samples = []
    
    def get_stats(self, current_time: float, window_sec: float) -> Dict[str, Any]:
        """
        Compute statistics for the window.
        
        Args:
            current_time: Current timestamp
            window_sec: Window duration in seconds
            
        Returns:
            Dictionary with:
            - above_count: Number of samples above threshold
            - total_count: Total samples in window
            - above_fraction: Fraction above threshold (0.0-1.0)
            - cumulative_above_sec: Total time above threshold
            - max_gap_sec: Longest gap below threshold
        """
        self.trim(window_sec, current_time)
        
        if not self.samples:
            return {
                "above_count": 0,
                "total_count": 0,
                "above_fraction": 0.0,
                "cumulative_above_sec": 0.0,
                "max_gap_sec": 0.0
            }
        
        # Count samples above threshold
        above_count = sum(1 for _, above in self.samples if above)
        total_count = len(self.samples)
        above_fraction = above_count / total_count if total_count > 0 else 0.0
        
        # Compute cumulative time above threshold
        cumulative_above_sec = 0.0
        for i in range(len(self.samples) - 1):
            if self.samples[i][1]:  # If above threshold
                duration = self.samples[i + 1][0] - self.samples[i][0]
                cumulative_above_sec += duration
        
        # Add last sample if above (estimate duration until now)
        if self.samples[-1][1]:
            duration = current_time - self.samples[-1][0]
            cumulative_above_sec += duration
        
        # Compute max gap below threshold
        max_gap_sec = 0.0
        current_gap = 0.0
        for i in range(len(self.samples) - 1):
            if not self.samples[i][1]:  # If below threshold
                duration = self.samples[i + 1][0] - self.samples[i][0]
                current_gap += duration
                max_gap_sec = max(max_gap_sec, current_gap)
            else:
                current_gap = 0.0
        
        return {
            "above_count": above_count,
            "total_count": total_count,
            "above_fraction": above_fraction,
            "cumulative_above_sec": cumulative_above_sec,
            "max_gap_sec": max_gap_sec
        }
