"""
DeskCoach Core Module
Background pose monitoring and metrics computation.
"""

from .pose_loop import PoseLoop
from .metrics import PostureMetrics, PostureState
from .calibration import CalibrationRoutine
from .storage import CalibrationStorage, CalibrationBaseline
from .state_machine import (
    PostureStateMachine,
    StateTransitionEvent,
    StateConfig,
    SensitivityPreset,
    SustainPolicy
)
from .nudge_config import NudgeConfig
from .notifications import NotificationEngine, NotificationAction
from .event_logger import EventLogger
from .policy import NotificationPolicy
from .status_bus import StatusBus, StatusSnapshot, create_snapshot_from_pose_loop
from .service_manager import ServiceManager, get_service_manager
from .calibration_status import CalibrationProgress, CalibrationProgressCallback, CalibrationStatusPublisher, read_calibration_status
from .calibration_runner import CalibrationRunner, get_calibration_runner
from .performance_config import PerformanceConfig, PerformanceMetrics
from .login_items import (
    is_login_item,
    add_login_item,
    remove_login_item,
    toggle_login_item,
    get_login_item_status
)

__all__ = [
    "PoseLoop",
    "PostureMetrics",
    "PostureState",
    "CalibrationRoutine",
    "CalibrationStorage",
    "CalibrationBaseline",
    "PostureStateMachine",
    "StateTransitionEvent",
    "StateConfig",
    "SensitivityPreset",
    "SustainPolicy",
    "NudgeConfig",
    "NotificationEngine",
    "NotificationAction",
    "EventLogger",
    "NotificationPolicy",
    "StatusBus",
    "StatusSnapshot",
    "create_snapshot_from_pose_loop",
    "ServiceManager",
    "get_service_manager",
    "CalibrationProgress",
    "CalibrationProgressCallback",
    "CalibrationStatusPublisher",
    "read_calibration_status",
    "CalibrationRunner",
    "get_calibration_runner",
    "PerformanceConfig",
    "PerformanceMetrics",
    "is_login_item",
    "add_login_item",
    "remove_login_item",
    "toggle_login_item",
    "get_login_item_status"
]
