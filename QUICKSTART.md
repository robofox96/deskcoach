# DeskCoach - Quick Start (M1)

## One-Time Setup

```bash
# 1. Install Python 3.12 (if not already installed)
brew install python@3.12

# 2. Create virtual environment with Python 3.12
/opt/homebrew/bin/python3.12 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

## Grant Camera Permission

On first run, macOS will prompt for camera permission:
- **System Settings** → **Privacy & Security** → **Camera**
- Enable for **Terminal** (or your IDE if running from IDE)

## Run Calibration (First Time)

```bash
# Activate venv (if not already active)
source venv/bin/activate

# Run calibration (sit upright for 25 seconds)
python dev_runner_calibrate.py

# Follow on-screen instructions:
#   1. Sit comfortably upright
#   2. Look straight ahead
#   3. Keep shoulders level
#   4. Stay still for 25 seconds
```

**Calibration captures your neutral posture baseline:**
- Neck flexion angle
- Torso flexion angle
- Lateral lean (shoulder asymmetry)
- Shoulder width proxy

**Baseline is saved to:** `storage/calibration.json`

## Run the Pose Loop

```bash
# Activate venv (if not already active)
source venv/bin/activate

# Run with defaults (8 FPS, camera 0, print every 2s)
python dev_runner.py

# Run with custom settings
python dev_runner.py --fps 6.0 --interval 3.0

# Stop with Ctrl+C
```

**After calibration, dev_runner will show:**
```
CALIBRATION STATUS: ✓ Calibrated
  Calibrated at: 2025-11-02T19:20:16
  Baselines: Neck=3.8°, Torso=2.3°, Lateral=0.018
```

## What You'll See

```
================================================================================
DeskCoach M1 - Pose Loop Dev Runner
================================================================================
Target FPS: 8.0
Camera: 0
Print interval: 2.0s

PRIVACY: No frames are saved. Only metrics are computed.

Press Ctrl+C to stop
================================================================================

Pose loop started (target 8.0 FPS)
[GOOD] Neck:  12.6° | Torso:   0.5° | Lateral: 0.098 | Conf: 0.67 | FPS:  7.5 | Frames: 15
[GOOD] Neck:   9.7° | Torso:   0.8° | Lateral: 0.082 | Conf: 0.67 | FPS:  7.5 | Frames: 30
...
```

## Metrics Explained

- **Neck:** Forward head angle (degrees from vertical)
- **Torso:** Forward lean angle (degrees from vertical)
- **Lateral:** Shoulder asymmetry (normalized ratio)
- **Conf:** Pose detection confidence (0-1)
- **FPS:** Actual frames per second
- **State:** GOOD (detecting) or PAUSED (low confidence)

## Troubleshooting

### Camera not accessible
- Grant camera permission in System Settings
- Restart terminal/IDE after granting permission
- Try different camera index: `--camera 1`

### Python version error
- MediaPipe requires Python ≤3.12
- Check version: `./venv/bin/python --version`
- Recreate venv with Python 3.12 if needed

### High CPU usage
- Lower FPS: `--fps 6.0`
- Normal range: 15-20% on M1/M2 Macs

### No pose detected (always PAUSED)
- Ensure you're visible in webcam
- Check lighting (avoid backlight)
- Sit closer to camera
- Verify camera is working: `open /Applications/Photo\ Booth.app`

## Recalibration

To recalibrate (e.g., after changing desk setup):

```bash
python dev_runner_calibrate.py

# Will prompt: "Re-calibrate? This will overwrite existing baseline. (y/N):"
# Type 'y' to proceed
```

## Next Steps

After calibration:
1. ✅ Pose loop working
2. ✅ Calibration complete
3. ⏭️ Implement state machine for posture issue detection
4. ⏭️ Add notification system
5. ⏭️ Build settings UI

## Privacy Reminder

✅ No images or video frames are ever saved  
✅ Only computed metrics (angles, timestamps) are stored  
✅ All processing happens locally on your machine  
✅ No network calls or cloud uploads
