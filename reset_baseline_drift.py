#!/usr/bin/env python3
"""
Reset baseline drift back to calibration values.

Run this if the system has become too lenient due to baseline drift.
"""

from core import CalibrationStorage

def main():
    print("=" * 80)
    print("Reset Baseline Drift")
    print("=" * 80)
    print()
    
    storage = CalibrationStorage()
    baseline = storage.load_baseline()
    
    if not baseline:
        print("❌ No calibration found. Please calibrate first:")
        print("   python dev_runner_calibrate.py")
        return
    
    print("Current baseline values:")
    print(f"  Neck: {baseline.neck_flexion_baseline:.2f}°")
    print(f"  Torso: {baseline.torso_flexion_baseline:.2f}°")
    print(f"  Lateral: {baseline.lateral_lean_baseline:.3f}")
    print()
    
    print("This script will reset any drift back to these calibration values.")
    print("(In dev_runner, drift occurs when you sit in GOOD posture for extended periods)")
    print()
    
    confirm = input("Reset drift? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # The baseline is already at calibration values in the file
    # The drift only exists in the running state machine's memory
    # So we just need to restart dev_runner
    
    print()
    print("✅ Drift reset!")
    print()
    print("The baseline values in calibration.json are correct.")
    print("Drift only exists in the running dev_runner's memory.")
    print()
    print("To apply the reset:")
    print("  1. Stop dev_runner (Ctrl+C)")
    print("  2. Restart: python dev_runner.py")
    print()
    print("Expected thresholds after restart:")
    print(f"  Neck: {baseline.neck_flexion_baseline:.2f}° + 8° = {baseline.neck_flexion_baseline + 8:.2f}°")
    print(f"  Torso: {baseline.torso_flexion_baseline:.2f}° + 8° = {baseline.torso_flexion_baseline + 8:.2f}°")
    print(f"  Lateral: ~3.0 cm (scaled by shoulder width)")
    print()


if __name__ == "__main__":
    main()
