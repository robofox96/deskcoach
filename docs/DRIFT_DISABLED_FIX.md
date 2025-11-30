# Baseline Drift Disabled - Critical Fix

**Date:** 2025-11-02  
**Issue:** Runaway threshold increases preventing detection  
**Status:** ✅ FIXED

---

## Problem

Baseline drift was causing **runaway threshold increases** that made posture detection impossible.

### Observed Behavior

User slouches to 18° for 60 seconds:

```
Time: 0s   → Neck: 4.5°,  Threshold: 13.5° (5.5+8)  ✓ Good posture
Time: 43s  → Neck: 19.4°, Threshold: 14.2° (6.2+8)  → Slouching!
Time: 45s  → Neck: 17.2°, Threshold: 15.1° (7.1+8)  → Still slouching
Time: 51s  → Neck: 18.5°, Threshold: 17.3° (9.3+8)  → Still slouching
Time: 53s  → Neck: 18.7°, Threshold: 17.9° (9.9+8)  → Still slouching
Time: 61s  → Neck: 18.2°, Threshold: 20.3° (12.3+8) ✓ Under threshold again!
```

**Baseline drifted from 5.5° to 12.3° in just 61 seconds!**

The threshold kept increasing, eventually overtaking the user's slouch angle, making detection impossible.

---

## Root Cause

The drift mechanism was designed to slowly adapt to changes in "normal" posture over days/weeks. However, it had a fatal flaw:

**Drift was applied EVERY FRAME while in GOOD state**, even when the user was slouching (but still below threshold).

### The Runaway Loop

1. **Calibration**: Baseline = 10°, Threshold = 18°
2. **User slouches to 17°**: Still GOOD (17° < 18°)
3. **Drift applies**: `baseline = baseline * (1 - 0.005) + current_metric * 0.005`
   - New baseline: 10° * 0.995 + 17° * 0.005 = 10.035°
4. **Next frame**: User still at 17°, baseline now 10.035°
   - Drift again: 10.035° * 0.995 + 17° * 0.005 = 10.070°
5. **After 100 frames** (~13 seconds at 8 FPS):
   - Baseline drifted to 11.5°
   - Threshold now 19.5°
   - User's 17° is no longer close to threshold
6. **After 500 frames** (~60 seconds):
   - Baseline drifted to 13.5°
   - Threshold now 21.5°
   - User would need to slouch to 21.5°+ to trigger!

### Why This Happened

The drift was intended for **very long-term adaptation** (days/weeks), but was applied at **per-frame granularity** (8 times per second).

**Math:**
- Drift per frame: 0.005 (0.5%)
- Frames per second: 8
- **Effective drift rate: 4% per second** toward current posture
- Time to drift halfway to current posture: ~17 seconds

This is **WAY too fast** for long-term adaptation.

---

## Solution

**Disable baseline drift entirely for M1.**

### Code Change

File: `core/state_machine_config.py`

```python
# Before
drift_alpha: float = 0.005  # Drift enabled

# After
drift_alpha: float = 0.0  # Drift DISABLED
```

### Why Disable Instead of Fix?

**Option 1: Disable Drift** (Chosen)
- ✅ Simple, safe fix
- ✅ Predictable behavior
- ✅ Users can recalibrate if baseline is wrong
- ❌ No long-term adaptation

**Option 2: Fix Drift Rate** (Rejected for M1)
- Set drift_alpha = 0.0001 (100x slower)
- Only apply drift after X minutes in GOOD
- Only apply drift when metrics are very close to baseline
- More complex, needs testing

We chose **Option 1** for M1 because:
1. Safer - can't cause runaway behavior
2. Simpler - no complex logic needed
3. Recalibration is easy if baseline changes

**Option 2 can be explored for M2** with proper testing.

---

## Impact

### Before (Drift Enabled)

**Scenario**: User slouches to 18° for 60 seconds

```
Start:  Baseline 5.5°, Threshold 13.5°  → Slouching detected ✓
20s:    Baseline 8.0°, Threshold 16.0°  → Still slouching ✓
40s:    Baseline 10.5°, Threshold 18.5° → Still slouching ✓
60s:    Baseline 12.5°, Threshold 20.5° → No longer slouching! ✗
```

**Result:** False negative - user is slouching but system says GOOD

### After (Drift Disabled)

**Scenario**: User slouches to 18° for 60 seconds

```
Start:  Baseline 5.5°, Threshold 13.5°  → Slouching detected ✓
20s:    Baseline 5.5°, Threshold 13.5°  → Still slouching ✓
40s:    Baseline 5.5°, Threshold 13.5°  → Still slouching ✓
60s:    Baseline 5.5°, Threshold 13.5°  → Still slouching ✓
```

**Result:** Correct detection throughout

---

## Testing

### Test Case 1: Normal Slouch Detection

```bash
./venv/bin/python dev_runner.py --diagnostics
```

**Steps:**
1. Sit upright for 10 seconds
2. Slouch heavily (neck > 18°) for 30 seconds
3. Return to upright

**Expected:**
- State changes to SLOUCH after 30s
- Notification appears
- Baseline stays constant throughout

**Verify:**
```
[GOOD]   Neck: 10.0°, Threshold: 17.9° (9.9+8)
[GOOD]   Neck: 18.5°, Threshold: 17.9° (9.9+8) ← Threshold unchanged
[SLOUCH] Neck: 18.5°, Threshold: 17.9° (9.9+8) ← Still unchanged
```

### Test Case 2: Long Session

```bash
./venv/bin/python dev_runner.py
```

**Steps:**
1. Run for 30 minutes
2. Alternate between good posture and slouching

**Expected:**
- Baseline stays at calibration value (~10°)
- Threshold stays at ~18°
- Consistent detection throughout session

**Check logs:**
```bash
grep "Thresholds" storage/events.jsonl | head -1
grep "Thresholds" storage/events.jsonl | tail -1
# Should show same threshold values
```

### Test Case 3: Baseline Verification

**At startup:**
```
Calibration: Neck=9.9°, Torso=0.5°
```

**After 10 minutes:**
```
[GOOD] Neck: 10.0° | ...
  Thresholds: Neck=17.9° (9.9+8), ...
```

**Baseline should be unchanged** (9.9° start = 9.9° after 10 min)

---

## When to Recalibrate

Baseline drift was intended to handle gradual posture changes over time. With drift disabled, users need to manually recalibrate if their baseline changes significantly.

### Recalibration Indicators

**Recalibrate if:**
1. **Too sensitive** - Getting nudges when sitting normally
   - Baseline is too low for your current "normal" posture
2. **Not sensitive enough** - No nudges even when slouching badly
   - Baseline is too high for your current "normal" posture
3. **After major change** - New chair, desk height, monitor position
   - Your ergonomics changed, need new baseline

### How to Recalibrate

```bash
./venv/bin/python dev_runner_calibrate.py
```

Follow prompts to capture new baseline.

---

## Future: Smart Drift (M2)

For M2, we can implement smarter drift that avoids runaway:

### Option 1: Time-Gated Drift

Only apply drift after sustained GOOD posture:

```python
if state == GOOD and time_in_good > 600:  # 10 minutes
    if abs(current - baseline) < 2.0:  # Very close to baseline
        baseline = baseline * 0.9999 + current * 0.0001  # 100x slower
```

### Option 2: Bounded Drift

Limit how far baseline can drift from calibration:

```python
max_drift = 3.0  # degrees
if abs(drift_baseline - calibration_baseline) < max_drift:
    apply_drift()
```

### Option 3: User-Controlled Drift

Let user enable/disable drift in UI:

```python
if user_settings.enable_drift and time_in_good > 1800:  # 30 min
    apply_drift()
```

### Option 4: Weekly Baseline Update

Instead of continuous drift, update baseline weekly:

```python
if time_since_last_update > 7 * 24 * 3600:  # 1 week
    if median_posture_over_week < calibration_baseline + 5.0:
        prompt_user_to_recalibrate()
```

---

## Summary

**Problem:** Baseline drift caused runaway threshold increases, making detection impossible.

**Root Cause:** Drift was applied per-frame (8x/sec) instead of over long periods (days/weeks).

**Fix:** Disabled drift entirely for M1 (`drift_alpha = 0.0`).

**Impact:**
- ✅ Stable, predictable detection
- ✅ Consistent thresholds throughout session
- ❌ No automatic adaptation (manual recalibration needed)

**Testing:** Verify baseline stays constant, detection works reliably.

**Future:** Implement smarter drift mechanism for M2.

---

**CRITICAL FIX APPLIED ✅**

Now test again - slouching should trigger reliably!
