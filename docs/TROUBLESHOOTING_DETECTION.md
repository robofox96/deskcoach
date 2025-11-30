# Troubleshooting Detection & Notification Issues

**Date:** 2025-11-02  
**Issues:** State not changing, notifications not appearing

---

## Issue 1: State Not Changing (Baseline Drift)

### Symptom

You're slouching but the state stays GOOD. Thresholds seem very high.

### Root Cause

**Baseline drift** has made the system too lenient.

Your calibration baseline was:
- Neck: 9.95°
- Torso: 0.46°

But the running baseline has drifted to:
- Neck: 13.5° (+3.5° drift!)
- Torso: 1.5° (+1° drift!)

This makes the effective threshold:
- **Original**: 9.95° + 8° = **17.95°** ✅
- **Current**: 13.5° + 8° = **21.5°** ❌ (too high!)

### Why Did This Happen?

Baseline drift is designed to slowly adapt to your "normal" posture over time. However, if you sit in a **slightly bad posture for an extended period while in GOOD state**, the baseline drifts upward.

**Example:**
- You calibrate at 10° neck flexion
- You sit at 13-14° for 5 minutes (still below 18° threshold, so state is GOOD)
- The drift alpha (0.005) slowly moves the baseline from 10° toward 13°
- After 5 minutes, baseline is now 13°
- Effective threshold is now 13° + 8° = 21°
- Now you need to slouch to 21°+ to trigger (much harder!)

### Quick Fix: Restart

**The drift is in-memory only**. Simply restart dev_runner:

```bash
# Stop dev_runner
Ctrl+C

# Restart
./venv/bin/python dev_runner.py
```

This resets the baseline back to calibration values (9.95°, 0.46°).

### Permanent Fix: Reduce Drift

Edit the drift alpha to make it slower:

**Option 1: In Code**

Edit `core/state_machine_config.py`:
```python
# Change from:
drift_alpha: float = 0.005

# To:
drift_alpha: float = 0.001  # 5x slower drift
```

**Option 2: Via Config (Future)**

In M2, you'll be able to adjust this in the UI settings.

**Option 3: Disable Drift**

Set drift_alpha to 0.0 to disable drift entirely:
```python
drift_alpha: float = 0.0  # No drift
```

### When to Recalibrate

If you find the baseline is consistently wrong (e.g., you're slouching at 12° but calibration is 10°, so you constantly trigger), recalibrate:

```bash
./venv/bin/python dev_runner_calibrate.py
```

---

## Issue 2: Notifications Not Appearing

### Symptom

"nudged" events appear in logs and terminal, but no notification popup on screen.

### Possible Causes

#### Cause 1: macOS Notification Permissions

**Check:**
1. Open **System Settings → Notifications**
2. Find "**Terminal**" or "**Python**" in the list
3. Ensure:
   - ☑ Allow Notifications
   - Alert style: **Banners** or **Alerts**
   - ☑ Show previews: **Always**

**Note:** Permissions are per-app. If running from Terminal, give Terminal permissions. If running as Python script, give Python permissions.

#### Cause 2: Do Not Disturb / Focus Mode

**Check:**
```bash
# Check if DND is active
defaults read com.apple.notificationcenterui doNotDisturb

# Output:
# 0 = DND off (notifications will show)
# 1 = DND on (notifications queued or suppressed)
```

**Fix:**
- Disable DND/Focus mode temporarily
- Or run with `--no-dnd-check` flag:
  ```bash
  ./venv/bin/python dev_runner.py --no-dnd-check
  ```

#### Cause 3: Notification De-dupe

The system won't re-nudge the **same state** within 20 minutes (dedupe window).

**Example:**
```
22:00 - LATERAL_LEAN detected → nudge posted ✅
22:05 - LATERAL_LEAN again → suppressed (dedupe) ❌
22:21 - LATERAL_LEAN again → nudge posted ✅ (20 min passed)
```

**But different states are independent:**
```
22:00 - LATERAL_LEAN → nudge ✅
22:05 - SLOUCH → nudge ✅ (different state, not affected by dedupe)
```

**Check logs:**
```bash
tail -20 storage/events.jsonl | jq -r '[.timestamp, .event_type, .state, .metadata.suppression_type // ""] | @tsv'
```

Look for `suppressed` events with `suppression_type`.

#### Cause 4: Terminal-Notifier Not Working

**Test directly:**
```bash
terminal-notifier -title "Test" -message "Hello" -group "DeskCoach"
```

**Expected:** Notification appears immediately.

**If not:**
```bash
# Check if installed
which terminal-notifier

# If not found:
brew install terminal-notifier
```

#### Cause 5: Policy Not Calling Notification

With the updated code, you should see debug output when a notification is attempted:

```
[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Neck 19.5° > 16.4° (73% of last 30s)
[POLICY] ✅ Notification posted successfully!
```

**If you DON'T see this**, the policy is suppressing the nudge. Check for:
```
[POLICY] Nudge suppressed: <reason>
```

Common reasons:
- `global_cooldown` - You clicked "Done" recently (30 min cooldown)
- `snooze` - You clicked "Snooze" recently (15 min)
- `dedupe_window` - Same state within 20 min
- `active_notification_exists` - Previous notification still showing

---

## Debugging Workflow

### Step 1: Verify Calibration

```bash
cat storage/calibration.json | jq .baseline
```

**Expected output:**
```json
{
  "neck_flexion_baseline": 9.95,
  "torso_flexion_baseline": 0.46,
  "lateral_lean_baseline": 0.013,
  ...
}
```

These are your **original** calibration values. The running baseline may have drifted.

### Step 2: Check Current Thresholds

Run dev_runner with diagnostics:
```bash
./venv/bin/python dev_runner.py --diagnostics
```

Look for:
```
Thresholds: Neck=17.95° (9.95+8), Torso=8.46° (0.46+8), Lateral=0.050
```

The first number (9.95, 0.46) is the **current baseline** (may have drifted).
The second number (8) is the **delta** (fixed by preset).
The sum is the **effective threshold**.

**If the baseline has drifted significantly**, restart dev_runner.

### Step 3: Test Notification System

```bash
./venv/bin/python test_notification.py
```

**Expected:**
```
✅ Notification posted successfully!
```

**Check your notification center** - you should see 2 test notifications.

**If you don't see them:**
- Check macOS permissions (System Settings → Notifications)
- Check DND status
- Test terminal-notifier directly

### Step 4: Trigger a Real Nudge

```bash
./venv/bin/python dev_runner.py --diagnostics
```

**Slouch heavily** (neck > 18°) for 30+ seconds.

**Expected output:**
```
================================================================================
STATE TRANSITION: GOOD → SLOUCH
Reason: Slouch (majority): Neck 19.5° > 17.95° (73% of 30s, 22s total)
Time in previous state: 45.2s
Metrics: Neck=19.5°, Torso=2.1°, Lateral=0.023
================================================================================

[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Neck 19.5° > 17.95°
[POLICY] ✅ Notification posted successfully!

[SLOUCH] Neck:  19.5° | ...
```

**Check notification center** - you should see the posture notification.

### Step 5: Check Event Log

```bash
tail -10 storage/events.jsonl | jq .
```

**Expected:**
```json
{
  "timestamp": "2025-11-02T22:30:15.123",
  "event_type": "nudged",
  "state": "slouch",
  "reason": "Slouch (majority): Neck 19.5° > 17.95° ...",
  ...
}
```

---

## Common Scenarios

### Scenario 1: "I'm slouching but state stays GOOD"

**Diagnosis:**
- Check current threshold in diagnostics output
- Compare your neck angle to threshold
- If threshold is > 20°, baseline has drifted

**Fix:**
1. Restart dev_runner (resets drift)
2. Or reduce drift_alpha in config
3. Or recalibrate

### Scenario 2: "State changed but no notification"

**Diagnosis:**
- Check terminal output for "[POLICY]" lines
- Look for "Nudge suppressed" or "Notification posted"
- Check event log for "suppressed" events

**Fix:**
- If suppressed by dedupe: Try a **different state** (slouch vs lateral)
- If suppressed by cooldown: Wait for cooldown to expire
- If notification posted but not visible: Check macOS permissions

### Scenario 3: "First nudge works, then none"

**Cause:** De-dupe window (20 min)

**Fix:**
- Wait 20 minutes
- Or try a different state
- Or disable dedupe: `--cooldowns off`

### Scenario 4: "Notifications worked before, now don't"

**Possible causes:**
- DND/Focus mode enabled
- macOS permissions revoked
- terminal-notifier uninstalled (e.g., after brew update)

**Fix:**
- Check DND status
- Check System Settings → Notifications
- Reinstall: `brew install terminal-notifier`

---

## Configuration Tuning

### Make Detection More Sensitive

**Option 1: Lower thresholds**

Edit preset or use UI:
```python
slouch_threshold_deg = 6.0  # (default: 8.0)
forward_lean_threshold_deg = 6.0
```

**Option 2: Shorter detection windows**

```python
slouch_policy.window_sec = 20.0  # (default: 30.0)
slouch_policy.majority_fraction = 0.55  # (default: 0.60)
```

### Make Detection Less Sensitive

**Option 1: Higher thresholds**

```python
slouch_threshold_deg = 10.0  # (default: 8.0)
```

**Option 2: Longer detection windows**

```python
slouch_policy.window_sec = 40.0  # (default: 30.0)
slouch_policy.majority_fraction = 0.70  # (default: 0.60)
```

### Reduce Notification Frequency

**Option 1: Longer cooldowns**

```python
cooldown_done_sec = 3600.0  # 60 min (default: 30 min)
```

**Option 2: Longer dedupe**

```python
dedupe_window_sec = 1800.0  # 30 min (default: 20 min)
```

### Disable Drift

```python
drift_alpha = 0.0  # (default: 0.005)
```

---

## Quick Reference

### Test Commands

```bash
# Test notification system
./venv/bin/python test_notification.py

# Test notification directly
terminal-notifier -title "Test" -message "Hello"

# Check calibration
cat storage/calibration.json | jq .baseline

# Check event log
tail -20 storage/events.jsonl | jq .

# Check DND status
defaults read com.apple.notificationcenterui doNotDisturb

# Run with debug output
./venv/bin/python dev_runner.py --diagnostics

# Run without DND check
./venv/bin/python dev_runner.py --no-dnd-check

# Run without cooldowns (testing)
./venv/bin/python dev_runner.py --cooldowns off
```

### File Locations

- **Calibration**: `storage/calibration.json`
- **Event log**: `storage/events.jsonl`
- **Config** (future): `storage/ui_config.json`

### Key Metrics

- **Calibration baseline**: Neck ~10°, Torso ~0.5°
- **Sensitive threshold**: Baseline + 8°
- **Detection window**: 30 seconds
- **Majority fraction**: 60% of window
- **Dedupe window**: 20 minutes
- **Done cooldown**: 30 minutes
- **Drift alpha**: 0.005 (very slow)

---

## Summary

**Issue 1: State Not Changing**
- **Cause:** Baseline drift made thresholds too high
- **Fix:** Restart dev_runner, or reduce drift_alpha

**Issue 2: Notifications Not Appearing**
- **Cause:** macOS permissions, DND, or dedupe
- **Fix:** Check permissions, disable DND, or wait for dedupe

**Quick Test:**
```bash
# 1. Restart to reset drift
./venv/bin/python dev_runner.py --diagnostics

# 2. Slouch heavily for 30s
# Expected: State changes to SLOUCH, notification appears

# 3. If notification doesn't appear, check:
#    - Terminal output for "[POLICY]" debug lines
#    - System Settings → Notifications
#    - DND status
```

---

**Next Steps:**
1. Restart dev_runner to reset drift
2. Check notification permissions
3. Test with heavy slouch (neck > 18°)
4. Report results
