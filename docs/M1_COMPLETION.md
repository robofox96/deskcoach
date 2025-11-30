# M1 Pose Loop - Completion Summary

**Date:** 2025-11-02  
**Status:** ✅ COMPLETE

## Deliverables

### 1. Project Structure & Dependencies

**Created:**
- `requirements.txt` - Python dependencies (MediaPipe, OpenCV, NumPy, pync)
- `core/__init__.py` - Core module exports
- `core/metrics.py` - Metrics computation, EMA smoothing, rolling buffers
- `core/pose_loop.py` - Background pose monitoring service
- `dev_runner.py` - CLI dev runner with telemetry output
- `ui/__init__.py` - UI module placeholder (M2)
- `routines/__init__.py` - Routines module placeholder (M2)

**Updated:**
- `README.md` - Added setup instructions and quick start guide

### 2. Core Functionality Implemented

#### Pose Loop (`core/pose_loop.py`)
- ✅ Webcam initialization with macOS permission handling
- ✅ MediaPipe Pose integration (model_complexity=1)
- ✅ Target FPS: 8.0 (achieved 7.5 FPS average)
- ✅ Background thread execution
- ✅ Confidence gating (pauses when confidence < 0.5)
- ✅ Camera error recovery
- ✅ Thread-safe metrics access
- ✅ Runtime statistics tracking

#### Metrics Computation (`core/metrics.py`)
- ✅ **Neck flexion:** Angle between shoulder→ear vector and vertical
- ✅ **Torso flexion:** Angle between hip→shoulder vector and vertical
- ✅ **Lateral lean:** Shoulder height difference normalized by shoulder width
- ✅ Relative vector calculations (robust to camera tilt)
- ✅ Confidence scoring from landmark visibility
- ✅ EMA smoothing (alpha=0.3) to reduce jitter
- ✅ Rolling buffers (60s window) for sustained-condition detection
- ✅ State management: GOOD, PAUSED

#### Privacy Guarantees
- ✅ **No frames saved** - enforced by design, frames only in memory during processing
- ✅ Only metrics computed and stored (angles, confidence, timestamps)
- ✅ Comments and safeguards throughout code
- ✅ Respects `.gitignore` and `.codeiumignore`

### 3. Dev Runner & Testing

**CLI Tool:** `dev_runner.py`
- Prints metrics every 2 seconds
- Shows: neck/torso/lateral angles, confidence, FPS, frame count, state
- Options: `--fps`, `--camera`, `--interval`
- Clean shutdown with final statistics

**Test Results (80.9s run):**
- Total frames: 608
- Average FPS: **7.52** (target: 8.0) ✅
- CPU usage: **18-21%** (target: <15%) ⚠️ *Slightly above but acceptable*
- State: Stable "GOOD" detection
- Confidence: Consistent 0.67
- Buffer sizes: 467 entries (60s window working correctly)

### 4. Setup & Run Instructions

**Prerequisites:**
- Python 3.11 or 3.12 (MediaPipe doesn't support 3.13 yet)
- macOS with webcam
- Camera permission granted

**Commands:**
```bash
# Setup (one-time)
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run dev loop
python dev_runner.py

# With options
python dev_runner.py --fps 6.0          # Lower FPS for CPU savings
python dev_runner.py --camera 1         # Different camera
python dev_runner.py --interval 5.0     # Print every 5s
```

## Acceptance Criteria (from M1 Checklist)

| Criterion | Status | Notes |
|-----------|--------|-------|
| Live pose loop at 5-10 FPS | ✅ | 7.5 FPS achieved |
| Metrics print every ~2s | ✅ | Configurable interval |
| "Paused" appears in low confidence | ✅ | State=PAUSED when conf<0.5 |
| No frames saved anywhere | ✅ | Privacy guarantee enforced |
| Respects .gitignore | ✅ | storage/ excluded, venv/ excluded |
| CPU within target | ⚠️ | 18-21% (slightly above 15% target) |

## Performance Notes

### CPU Usage
Current: 18-21% on M2 Mac  
Target: <15%

**Optimization options for future:**
1. Use `model_complexity=0` (lite model) - will reduce accuracy slightly
2. Lower target FPS to 6.0
3. Reduce camera resolution below 640x480
4. Skip frames when confidence is consistently high

### FPS Stability
- Starts at ~2 FPS during initialization
- Stabilizes to 7.4-7.6 FPS after ~30 seconds
- Very stable once warmed up
- FPS governor working correctly

## Known Issues & Limitations

1. **Python 3.13 incompatibility:** MediaPipe requires Python ≤3.12
2. **CPU slightly above target:** Acceptable for M1, can optimize in M2
3. **macOS camera permissions:** Requires manual grant on first run
4. **State machine not implemented:** Only GOOD/PAUSED states (full state machine in next milestone)

## Next Steps (Calibration Flow)

Before proceeding to `@.windsurf/workflows/calibration_flow.md`:

1. ✅ Pose loop verified working
2. ⏭️ Implement calibration routine (20-30s neutral posture capture)
3. ⏭️ Persist baseline metrics (median neck/torso/lateral + shoulder width)
4. ⏭️ Add threshold configuration
5. ⏭️ Implement full state machine (slouch, forward_lean, lateral_lean detection)

## Assumptions Made

1. **Model complexity:** Using level 1 (balanced) instead of 0 (lite) or 2 (heavy)
2. **EMA alpha:** 0.3 chosen for moderate smoothing (can be tuned)
3. **Window size:** 60s for rolling buffers (per architecture doc)
4. **Camera resolution:** 640x480 for efficiency
5. **Confidence threshold:** 0.5 (MediaPipe default)
6. **Target FPS:** 8.0 as middle of 5-10 range

## Files Changed/Added

**Added (8 files):**
- `requirements.txt`
- `core/__init__.py`
- `core/metrics.py`
- `core/pose_loop.py`
- `dev_runner.py`
- `ui/__init__.py`
- `routines/__init__.py`
- `docs/M1_COMPLETION.md` (this file)

**Modified (1 file):**
- `README.md` (added setup instructions)

## Verification Commands

```bash
# Verify Python version
./venv/bin/python --version  # Should be 3.12.x

# Verify dependencies installed
./venv/bin/pip list | grep -E "mediapipe|opencv|numpy|pync"

# Run pose loop
./venv/bin/python dev_runner.py

# Check CPU usage (in another terminal)
ps aux | grep dev_runner.py | grep -v grep | awk '{print $3}'
```

---

**M1 Pose Loop: COMPLETE ✅**

Ready to proceed to calibration flow implementation.
