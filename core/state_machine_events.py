"""
State machine events and data structures.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class StateTransitionEvent:
    """
    Event emitted when state changes.
    
    Contains all relevant information about the transition for logging
    and notification purposes.
    """
    timestamp: str  # ISO format
    from_state: str
    to_state: str
    reason: str
    time_in_previous_state: float  # seconds
    metrics_snapshot: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
