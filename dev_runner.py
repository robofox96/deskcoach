#!/usr/bin/env python3
"""
DeskCoach M1 Development Runner
Runs the pose loop and prints metrics every 2 seconds for manual verification.

Usage:
    python dev_runner.py [--fps FPS] [--camera INDEX]
"""

import os
import argparse
import time
import sys

# Set environment variable for macOS camera permission handling
os.environ['OPENCV_AVFOUNDATION_SKIP_AUTH'] = '1'

from core import (PoseLoop, CalibrationStorage, StateTransitionEvent, StateConfig, SensitivityPreset,
                  NotificationPolicy, NudgeConfig, NotificationEngine, EventLogger, NotificationAction)
from core.status_bus import StatusBus, create_snapshot_from_pose_loop
from core.performance_config import PerformanceConfig


# Global state for tracking transitions
transition_events = []
policy_engine = None
status_bus = None
pose_loop_instance = None
state_machine_instance = None
current_preset = "sensitive"

def state_transition_callback(event: StateTransitionEvent):
    """Callback for state transitions."""
    global policy_engine
    
    transition_events.append(event)
    print()
    print("=" * 80)
    print(f"STATE TRANSITION: {event.from_state.upper()} → {event.to_state.upper()}")
    print(f"Reason: {event.reason}")
    print(f"Time in previous state: {event.time_in_previous_state:.1f}s")
    print(f"Metrics: Neck={event.metrics_snapshot['neck_flexion']:.1f}°, "
          f"Torso={event.metrics_snapshot['torso_flexion']:.1f}°, "
          f"Lateral={event.metrics_snapshot['lateral_lean']:.3f}")
    print("=" * 80)
    print()
    
    # Pass to policy engine if available
    if policy_engine:
        diagnostics = None
        # Try to get diagnostics from state machine
        # This would need to be passed through, for now use None
        policy_engine.on_state_transition(event, diagnostics)

def format_metrics_line(metrics, stats, baseline=None, show_diagnostics=False):
    """Format a single line of metrics output."""
    if metrics is None:
        return f"[{stats['state'].upper()}] No metrics | FPS: {stats['actual_fps']:.1f}"
    
    line = (
        f"[{metrics.state.value.upper()}] "
        f"Neck: {metrics.neck_flexion:5.1f}° | "
        f"Torso: {metrics.torso_flexion:5.1f}° | "
        f"Lateral: {metrics.lateral_lean:5.3f} | "
        f"Conf: {metrics.confidence:4.2f} | "
        f"FPS: {stats['actual_fps']:4.1f} | "
        f"Frames: {stats['frames_processed']}"
    )
    
    # Add state machine info if available
    if 'state_machine' in stats:
        sm = stats['state_machine']
        line += f" | InState: {sm['time_in_state']:.0f}s"
    
    return line

def print_diagnostics(pose_loop):
    """Print diagnostic information about condition windows."""
    state_machine = pose_loop.get_state_machine()
    if not state_machine:
        return
    
    diag = state_machine.get_condition_diagnostics()
    
    print(f"  Thresholds: Neck={diag['slouch']['threshold']:.1f}° "
          f"({diag['slouch']['baseline']:.1f}+{diag['slouch']['delta']:.0f}), "
          f"Torso={diag['forward_lean']['threshold']:.1f}° "
          f"({diag['forward_lean']['baseline']:.1f}+{diag['forward_lean']['delta']:.0f}), "
          f"Lateral={diag['lateral_lean']['threshold']:.3f}")
    
    # Slouch diagnostics
    s = diag['slouch']
    majority_met = "[MAJORITY MET]" if s['above_fraction'] >= 0.60 and s['max_gap_sec'] <= 3.0 else ""
    cumulative_met = "[CUMULATIVE MET]" if s['cumulative_above_sec'] >= 18.0 else ""
    print(f"  Slouch: {s['above_fraction']:.0%} above ({s['cumulative_above_sec']:.0f}s total, "
          f"max_gap={s['max_gap_sec']:.1f}s) {majority_met}{cumulative_met}")
    
    # Forward lean diagnostics
    f = diag['forward_lean']
    majority_met = "[MAJORITY MET]" if f['above_fraction'] >= 0.60 and f['max_gap_sec'] <= 3.0 else ""
    cumulative_met = "[CUMULATIVE MET]" if f['cumulative_above_sec'] >= 18.0 else ""
    print(f"  Forward: {f['above_fraction']:.0%} above ({f['cumulative_above_sec']:.0f}s total, "
          f"max_gap={f['max_gap_sec']:.1f}s) {majority_met}{cumulative_met}")
    
    # Lateral lean diagnostics
    l = diag['lateral_lean']
    majority_met = "[MAJORITY MET]" if l['above_fraction'] >= 0.60 and l['max_gap_sec'] <= 3.0 else ""
    cumulative_met = "[CUMULATIVE MET]" if l['cumulative_above_sec'] >= 24.0 else ""
    print(f"  Lateral: {l['above_fraction']:.0%} above ({l['cumulative_above_sec']:.0f}s total, "
          f"max_gap={l['max_gap_sec']:.1f}s) {majority_met}{cumulative_met}")
    
    # Preset info
    summary = state_machine.get_state_summary()
    print(f"  Preset: {summary['preset'].upper()}")

def print_policy_status():
    """Print notification policy status."""
    global policy_engine
    if not policy_engine:
        return
    
    status = policy_engine.get_policy_status()
    
    parts = []
    if status['cooldown_remaining_min'] > 0:
        parts.append(f"cooldown {status['cooldown_remaining_min']:.1f}m")
    if status['snooze_remaining_min'] > 0:
        parts.append(f"snooze {status['snooze_remaining_min']:.1f}m")
    if status['backoff_remaining_min'] > 0:
        parts.append(f"backoff {status['backoff_remaining_min']:.1f}m")
    if status['last_nudge_min_ago'] is not None:
        parts.append(f"last nudge {status['last_nudge_min_ago']:.1f}m ago")
    if status['active_state']:
        parts.append(f"state: {status['active_state'].upper()}")
    if status['queued_nudge']:
        parts.append("[QUEUED]")
    
    if parts:
        print(f"  [POLICY] {' | '.join(parts)}")

def main():
    parser = argparse.ArgumentParser(description="DeskCoach M1 Dev Runner")
    parser.add_argument("--fps", type=float, default=6.0, help="Target FPS (default: 6.0 lightweight)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--interval", type=float, default=2.0, help="Print interval in seconds (default: 2.0)")
    parser.add_argument("--preset", type=str, choices=["sensitive", "standard", "conservative"], 
                       default="sensitive", help="Sensitivity preset (default: sensitive)")
    parser.add_argument("--majority", type=float, help="Override majority fraction (0.5-0.8)")
    parser.add_argument("--diagnostics", action="store_true", help="Show detailed diagnostics every interval")
    parser.add_argument("--no-dnd-check", action="store_true", help="Disable DND checking (dev only)")
    parser.add_argument("--cooldowns", type=str, choices=["on", "off"], default="on", help="Enable/disable cooldowns")
    parser.add_argument("--dry-run", action="store_true", help="Log decisions but don't post notifications")
    parser.add_argument("--perf-profile", action="store_true", help="Enable performance profiling (print stats every 30s)")
    parser.add_argument("--perf-mode", type=str, choices=["lightweight", "quality", "performance"], 
                       default="lightweight", help="Performance mode (default: lightweight)")
    args = parser.parse_args()
    
    # Check calibration status
    storage = CalibrationStorage()
    cal_status = storage.get_calibration_status()
    
    # Create performance config
    perf_mode_map = {
        "lightweight": PerformanceConfig.lightweight,
        "quality": PerformanceConfig.quality,
        "performance": PerformanceConfig.performance
    }
    perf_config = perf_mode_map[args.perf_mode]()
    
    # Override FPS if explicitly set
    if args.fps != 6.0:
        perf_config.target_fps = args.fps
    
    # Enable profiling if requested
    if args.perf_profile:
        perf_config.enable_profiling = True
    
    print("=" * 80)
    print("DeskCoach M1 - Pose Loop Dev Runner")
    print("=" * 80)
    print(f"Performance mode: {args.perf_mode.upper()}")
    print(f"Target FPS: {perf_config.target_fps}")
    print(f"Camera: {args.camera}")
    print(f"Resolution: {perf_config.camera_width}×{perf_config.camera_height}")
    print(f"Model complexity: {perf_config.model_complexity} ({'lite' if perf_config.model_complexity == 0 else 'full'})")
    print(f"Frame skip: {'enabled' if perf_config.enable_frame_skip else 'disabled'}")
    print(f"Adaptive governor: {'enabled' if perf_config.enable_governor else 'disabled'}")
    print(f"Performance profiling: {'enabled' if perf_config.enable_profiling else 'disabled'}")
    print(f"Print interval: {args.interval}s")
    print()
    
    # Display calibration status
    if cal_status["calibrated"]:
        print("CALIBRATION STATUS: ✓ Calibrated")
        print(f"  Calibrated at: {cal_status['calibrated_at']}")
        print(f"  Baselines: Neck={cal_status['neck_baseline']:.1f}°, "
              f"Torso={cal_status['torso_baseline']:.1f}°, "
              f"Lateral={cal_status['lateral_baseline']:.3f}")
        baseline = storage.load_baseline()
        
        # Create state config from preset
        preset_map = {
            "sensitive": SensitivityPreset.SENSITIVE,
            "standard": SensitivityPreset.STANDARD,
            "conservative": SensitivityPreset.CONSERVATIVE
        }
        preset = preset_map[args.preset]
        
        # Apply overrides
        overrides = {}
        if args.majority is not None:
            if not (0.5 <= args.majority <= 0.8):
                print(f"ERROR: --majority must be between 0.5 and 0.8")
                sys.exit(1)
            overrides['recovery_majority_fraction'] = args.majority
            # Also update policies
            print(f"  Override: majority_fraction = {args.majority}")
        
        state_config = StateConfig.from_preset(preset, **overrides)
        if args.majority is not None:
            # Update policies with custom majority
            state_config.slouch_policy.majority_fraction = args.majority
            state_config.forward_lean_policy.majority_fraction = args.majority
            state_config.lateral_lean_policy.majority_fraction = args.majority
        
        print(f"  Preset: {args.preset.upper()}")
        
        # Create notification policy
        nudge_config = NudgeConfig()
        if args.no_dnd_check:
            nudge_config.respect_dnd = False
            print(f"  DND check: DISABLED (dev mode)")
        
        if args.cooldowns == "off":
            nudge_config.cooldown_done_sec = 0
            nudge_config.cooldown_snooze_sec = 0
            print(f"  Cooldowns: DISABLED")
        
        global policy_engine
        policy_engine = NotificationPolicy(
            state_config=state_config,
            nudge_config=nudge_config,
            dry_run=args.dry_run
        )
        
        if args.dry_run:
            print(f"  Mode: DRY RUN (no actual notifications)")
    else:
        print("CALIBRATION STATUS: ✗ Not calibrated")
        print("  Run 'python dev_runner_calibrate.py' to calibrate")
        baseline = None
        state_config = None
    
    print()
    print("PRIVACY: No frames are saved. Only metrics are computed.")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()
    
    # Initialize pose loop with state machine if calibrated
    global pose_loop_instance, state_machine_instance, status_bus, current_preset
    
    if baseline and state_config:
        # Create state machine with config
        from core.state_machine import PostureStateMachine
        state_machine = PostureStateMachine(baseline, state_config)
        state_machine_instance = state_machine
        
        pose_loop = PoseLoop(
            camera_index=args.camera,
            target_fps=perf_config.target_fps,
            ema_alpha=0.3,
            window_seconds=60.0,
            baseline=baseline,
            state_transition_callback=state_transition_callback,
            perf_config=perf_config
        )
        # Replace default state machine with configured one
        pose_loop.state_machine = state_machine
        pose_loop_instance = pose_loop
        current_preset = args.preset
    else:
        pose_loop = PoseLoop(
            camera_index=args.camera,
            target_fps=perf_config.target_fps,
            ema_alpha=0.3,
            window_seconds=60.0,
            baseline=baseline,
            state_transition_callback=state_transition_callback if baseline else None,
            perf_config=perf_config
        )
        pose_loop_instance = pose_loop
    
    # Initialize status bus for UI IPC
    if baseline and state_config and policy_engine:
        status_bus = StatusBus(update_interval_sec=1.0)
        status_bus.set_snapshot_provider(
            lambda: create_snapshot_from_pose_loop(
                pose_loop_instance,
                state_machine_instance,
                policy_engine,
                current_preset
            )
        )
        print("Status bus initialized (publishing to storage/status.json)")
    
    try:
        # Start the loop
        pose_loop.start()
        
        # Start status bus if configured
        if status_bus:
            status_bus.start()
            print("Status bus started (1 Hz updates)")
        
        # Give it a moment to initialize
        time.sleep(1.0)
        
        print("Pose loop running...")
        print()
        
        # Print metrics periodically
        last_print = time.time()
        
        while True:
            time.sleep(0.5)  # Check every 0.5s
            
            now = time.time()
            if now - last_print >= args.interval:
                # Get latest metrics and stats
                metrics = pose_loop.get_latest_metrics()
                stats = pose_loop.get_stats()
                
                # Print formatted line
                print(format_metrics_line(metrics, stats, baseline))
                
                # Print diagnostics if requested
                if args.diagnostics and baseline:
                    print_diagnostics(pose_loop)
                
                # Print policy status
                print_policy_status()
                
                # Check DND queue
                if policy_engine:
                    policy_engine.check_dnd_queue()
                
                last_print = now
    
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("Stopping pose loop...")
        
        # Stop status bus first
        if status_bus:
            status_bus.stop()
            print("Status bus stopped")
        
        pose_loop.stop()
        
        # Print final stats
        final_stats = pose_loop.get_stats()
        print()
        print("Final Statistics:")
        print(f"  Total frames: {final_stats['frames_processed']}")
        print(f"  Elapsed time: {final_stats['elapsed_seconds']:.1f}s")
        print(f"  Average FPS: {final_stats['actual_fps']:.2f}")
        print(f"  Target FPS: {final_stats['target_fps']}")
        print(f"  Buffer sizes: Neck={final_stats['neck_buffer_size']}, "
              f"Torso={final_stats['torso_buffer_size']}, "
              f"Lateral={final_stats['lateral_buffer_size']}")
        
        # Print state machine stats if available
        if 'state_counts' in final_stats:
            print()
            print("State Transition Summary:")
            counts = final_stats['state_counts']
            print(f"  GOOD: {counts.get('good', 0)} transitions")
            print(f"  SLOUCH: {counts.get('slouch', 0)} transitions")
            print(f"  FORWARD_LEAN: {counts.get('forward_lean', 0)} transitions")
            print(f"  LATERAL_LEAN: {counts.get('lateral_lean', 0)} transitions")
            print(f"  PAUSED: {counts.get('paused', 0)} transitions")
            print(f"  Total transitions: {len(transition_events)}")
            
            if transition_events:
                last_event = transition_events[-1]
                print()
                print("Last Transition:")
                print(f"  {last_event.from_state.upper()} → {last_event.to_state.upper()}")
                print(f"  Reason: {last_event.reason}")
        
        print()
        print("Pose loop stopped cleanly.")
        print("=" * 80)
        
        sys.exit(0)
    
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        pose_loop.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
