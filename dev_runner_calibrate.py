#!/usr/bin/env python3
"""
DeskCoach Calibration Runner
Runs calibration routine to establish neutral posture baseline.

Usage:
    python dev_runner_calibrate.py [--duration SECONDS] [--camera INDEX]
"""

import os
import argparse
import sys

from core.platform import is_macos

# Set environment variable for macOS camera permission handling
if is_macos():
    os.environ['OPENCV_AVFOUNDATION_SKIP_AUTH'] = '1'

from core import PoseLoop, CalibrationRoutine, CalibrationStorage
from core.calibration_status import CalibrationProgressCallback


def main():
    parser = argparse.ArgumentParser(description="DeskCoach Calibration Runner")
    parser.add_argument("--duration", type=float, default=25.0, help="Calibration duration in seconds (default: 25.0)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--fps", type=float, default=8.0, help="Target FPS (default: 8.0)")
    parser.add_argument("--force", action="store_true", help="Run without interactive prompts (overwrite existing baseline)")
    args = parser.parse_args()
    
    # Initialize storage
    storage = CalibrationStorage()
    
    # Check existing calibration
    status = storage.get_calibration_status()
    
    if status["calibrated"]:
        print("=" * 80)
        print("EXISTING CALIBRATION FOUND")
        print("=" * 80)
        print(f"Calibrated at: {status['calibrated_at']}")
        print(f"Neck baseline: {status['neck_baseline']:.2f}°")
        print(f"Torso baseline: {status['torso_baseline']:.2f}°")
        print(f"Lateral baseline: {status['lateral_baseline']:.3f}")
        print(f"Shoulder width: {status['shoulder_width']:.3f}")
        print(f"Samples: {status['sample_count']}")
        print(f"Confidence: {status['confidence_mean']:.2f}")
        print("=" * 80)
        print()

        if not args.force:
            response = input("Re-calibrate? This will overwrite existing baseline. (y/N): ")
            if response.lower() != 'y':
                print("Calibration cancelled.")
                sys.exit(0)
            print()
    
    # Initialize pose loop
    print("Initializing pose loop...")
    pose_loop = PoseLoop(
        camera_index=args.camera,
        target_fps=args.fps,
        ema_alpha=0.3,
        window_seconds=60.0
    )
    
    try:
        # Start pose loop
        pose_loop.start()
        
        # Wait for initialization and first frames
        import time
        print("Waiting for pose loop to initialize...")
        time.sleep(3)
        
        # Check if pose loop is working
        max_retries = 5
        for i in range(max_retries):
            stats = pose_loop.get_stats()
            if stats['frames_processed'] > 0:
                break
            print(f"  Waiting for frames... ({i+1}/{max_retries})")
            time.sleep(1)
        
        if stats['frames_processed'] == 0:
            print("ERROR: Pose loop not capturing frames. Check camera permissions.")
            sys.exit(1)
        
        print(f"Pose loop running at {stats['actual_fps']:.1f} FPS")
        print()
        
        # Initialize calibration routine
        calibration = CalibrationRoutine(
            pose_loop=pose_loop,
            storage=storage,
            duration_seconds=args.duration
        )
        
        # Initialize progress callback for UI
        progress_callback = CalibrationProgressCallback()
        progress_callback.set_duration(args.duration)
        
        # Run calibration
        baseline = calibration.run_calibration(progress_callback=progress_callback.update)
        
        if baseline is None:
            print()
            print("ERROR: Calibration failed")
            sys.exit(1)
        
        print()
        print("Next steps:")
        print("  1. Run 'python dev_runner.py' to see baseline in action")
        print("  2. Proceed to state machine implementation")
        print()
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print()
        print("Calibration interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        pose_loop.stop()


if __name__ == "__main__":
    main()
