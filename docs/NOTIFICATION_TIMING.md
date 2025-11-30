# Notification Timing & Throttling

**Date:** 2025-11-02  
**Status:** ✅ COMPLETE

---

## Overview

Multiple mechanisms control when notifications appear to prevent spam:

1. **Active Notification Lock** (10 seconds)
2. **Per-State De-dupe** (20 minutes)
3. **Global Cooldown** (30 minutes after Done)
4. **Snooze Window** (15 minutes after Snooze)
5. **Backoff Period** (60 minutes after Dismiss)

---

## 1. Active Notification Lock

**Duration:** 10 seconds  
**Scope:** All notifications

### Purpose

Prevents multiple notifications from appearing simultaneously or in rapid succession.

### Behavior

- **First nudge** → Posts notification, sets lock
- **Lock active** → All subsequent nudges suppressed
- **After 10 seconds** → Lock cleared automatically
- **Next nudge** → Can post again (subject to other rules)

### Why 10 Seconds?

macOS notifications auto-dismiss after ~5 seconds (banners) or stay until dismissed (alerts). 10 seconds ensures the previous notification has been seen/dismissed before posting another.

### Fix Applied

**Before:** Lock was never cleared → all subsequent nudges suppressed forever

**After:** Lock auto-clears after 10 seconds → subsequent nudges can post

```python
# In policy._should_nudge()
if self.notification_engine.has_active_notification():
    age = self.notification_engine.get_active_notification_age()
    if age and age > 10.0:  # 10 seconds timeout
        self.notification_engine.clear_active_notification()
```

---

## 2. Per-State De-dupe

**Duration:** 20 minutes (configurable)  
**Scope:** Per posture state (slouch, forward_lean, lateral_lean)

### Purpose

Prevents re-nudging the **same posture issue** repeatedly. If you slouch, get nudged, fix it, then slouch again 5 minutes later, you won't get nudged again (assuming you didn't click Done).

### Behavior

- **Slouch detected at 10:00** → Nudge posted ✓
- **Slouch detected at 10:05** → Suppressed (dedupe) ✗
- **Forward lean at 10:05** → Nudge posted ✓ (different state!)
- **Slouch detected at 10:21** → Nudge posted ✓ (20 min passed)

### Configuration

```python
# core/nudge_config.py
dedupe_window_sec: float = 1200.0  # 20 minutes
```

### High-Severity Bypass

High-severity posture issues can bypass the dedupe window:

```python
high_severity_bypass_dedupe: bool = True
```

**Example:**
- Moderate slouch at 10:00 → Nudged
- Severe slouch at 10:05 → Nudged (bypass dedupe)

---

## 3. Global Cooldown (Done Action)

**Duration:** 30 minutes (configurable)  
**Scope:** All notifications

### Purpose

After you click "Done" on a notification, you're acknowledging you fixed your posture. The system gives you a 30-minute grace period before nudging again (for any state).

### Behavior

- **Slouch at 10:00** → Nudged
- **User clicks "Done"** → 30 min cooldown starts
- **Any posture issue at 10:15** → Suppressed (cooldown) ✗
- **Any posture issue at 10:31** → Nudge posted ✓

### Configuration

```python
cooldown_done_sec: float = 1800.0  # 30 minutes
```

### Note

Done action is **not currently captured** in M1 (non-blocking notifications). For M1, this cooldown is effectively unused. Will be enabled in M2 with action callbacks.

---

## 4. Snooze Window

**Duration:** 15 minutes (configurable)  
**Scope:** All notifications

### Purpose

Similar to Done, but shorter. User says "remind me later" and gets a 15-minute break from all notifications.

### Behavior

- **Slouch at 10:00** → Nudged
- **User clicks "Snooze"** → 15 min snooze starts
- **Any posture issue at 10:10** → Suppressed (snooze) ✗
- **Any posture issue at 10:16** → Nudge posted ✓

### Configuration

```python
cooldown_snooze_sec: float = 900.0  # 15 minutes
```

### Note

Like Done, Snooze action is **not currently captured** in M1. Will be enabled in M2.

---

## 5. Backoff Period (Dismiss Action)

**Duration:** 60 minutes (configurable)  
**Scope:** All notifications (via threshold increase)

### Purpose

User clicks "Dismiss" → system becomes less sensitive for a while. Thresholds temporarily increase, making it harder to trigger nudges.

### Behavior

- **Normal threshold:** Neck > 18° triggers
- **User dismisses at 10:00** → Backoff starts
- **Backoff threshold:** Neck > 23° triggers (18° + 5° backoff)
- **Slouch to 20° at 10:10** → No nudge (20° < 23°) ✗
- **Slouch to 24° at 10:10** → Nudge posted (24° > 23°) ✓
- **Backoff expires at 11:00** → Thresholds return to normal

### Configuration

```python
dismiss_backoff_neck_deg: float = 5.0     # +5° to neck threshold
dismiss_backoff_torso_deg: float = 5.0    # +5° to torso threshold
dismiss_backoff_lateral_cm: float = 1.0   # +1cm to lateral threshold
dismiss_backoff_duration_sec: float = 3600.0  # 60 minutes
```

### Note

Dismiss action is **not currently captured** in M1. Will be enabled in M2.

---

## Decision Flow

When a posture issue is detected:

```
State Transition Detected (GOOD → SLOUCH)
    ↓
1. Check Global Cooldown (Done action)
    ↓ (pass)
2. Check Snooze Window
    ↓ (pass)
3. Check Active Notification Lock (10s)
    ↓ (pass)
4. Check Per-State De-dupe (20m)
    ↓ (pass)
5. Check Backoff Thresholds
    ↓ (pass)
6. POST NOTIFICATION ✓
```

If any check fails → suppress and log reason.

---

## Practical Examples

### Example 1: Normal Usage

```
10:00 - Slouch detected → Nudge ✓
        (First nudge, no restrictions)

10:05 - Slouch again → Suppressed (dedupe: 15m remaining)

10:05 - Forward lean → Nudge ✓ 
        (Different state, not affected by slouch dedupe)

10:06 - Forward lean again → Suppressed (dedupe: 14m remaining)

10:21 - Slouch again → Nudge ✓
        (20 min passed since first slouch nudge)

10:22 - Lateral lean → Nudge ✓
        (Different state)
```

### Example 2: With Done Action (M2)

```
10:00 - Slouch → Nudge ✓
10:01 - User clicks "Done" → 30 min cooldown

10:05 - Slouch → Suppressed (cooldown: 26m remaining)
10:15 - Forward lean → Suppressed (cooldown: 16m remaining)
10:25 - Lateral lean → Suppressed (cooldown: 6m remaining)

10:31 - Slouch → Nudge ✓ (cooldown expired)
```

### Example 3: Rapid Posture Changes

```
10:00:00 - Slouch → Nudge ✓ (active notification set)
10:00:05 - Forward lean → Suppressed (active notification: 5s old)
10:00:11 - Lateral lean → Nudge ✓ (active notification cleared at 10s)
10:00:22 - Slouch → Nudge ✓ (active notification cleared)
```

### Example 4: High-Severity Bypass

```
10:00 - Moderate slouch (neck 19°) → Nudge ✓
10:05 - Moderate slouch (neck 19°) → Suppressed (dedupe)
10:10 - SEVERE slouch (neck 28°) → Nudge ✓ (bypass dedupe!)
```

---

## M1 vs M2 Differences

### M1 (Current)

**Active Rules:**
- ✅ Active Notification Lock (10s)
- ✅ Per-State De-dupe (20m)
- ❌ Global Cooldown (action not captured)
- ❌ Snooze Window (action not captured)
- ❌ Backoff Period (action not captured)

**Effective Timing:**
- **Minimum time between nudges:** 10 seconds (active lock)
- **Minimum time for same state:** 20 minutes (dedupe)
- **Can nudge different states:** Every 10+ seconds

### M2 (Future)

**Active Rules:**
- ✅ Active Notification Lock (10s)
- ✅ Per-State De-dupe (20m)
- ✅ Global Cooldown (30m after Done)
- ✅ Snooze Window (15m after Snooze)
- ✅ Backoff Period (60m after Dismiss)

**Effective Timing:**
- User has full control via actions
- Can opt into longer quiet periods (Done, Snooze)
- Can make system less sensitive (Dismiss)

---

## Configuration

All timing values are configurable in `core/nudge_config.py`:

```python
class NudgeConfig:
    # Active notification timeout (auto-clear)
    active_notification_timeout_sec: float = 10.0
    
    # De-dupe window (per-state)
    dedupe_window_sec: float = 1200.0  # 20 minutes
    
    # Global cooldown (Done action)
    cooldown_done_sec: float = 1800.0  # 30 minutes
    
    # Snooze window
    cooldown_snooze_sec: float = 900.0  # 15 minutes
    
    # Dismiss backoff
    dismiss_backoff_duration_sec: float = 3600.0  # 60 minutes
    dismiss_backoff_neck_deg: float = 5.0
    dismiss_backoff_torso_deg: float = 5.0
    dismiss_backoff_lateral_cm: float = 1.0
    
    # High-severity bypass
    high_severity_bypass_dedupe: bool = True
```

---

## Troubleshooting

### "I'm not getting any notifications"

**Check:**
1. Is there an active notification lock? (Wait 10 seconds)
2. Is state within dedupe window? (Try different state)
3. Are macOS permissions granted?
4. Is DND/Focus mode active?

### "I'm getting too many notifications"

**Adjust:**
- Increase `dedupe_window_sec` (e.g., 30 minutes)
- Increase detection thresholds
- Use higher sensitivity preset (Conservative)

### "I'm not getting enough notifications"

**Adjust:**
- Decrease `dedupe_window_sec` (e.g., 10 minutes)
- Decrease detection thresholds
- Use lower sensitivity preset (Sensitive)

### "Notifications stopped after the first one"

**This was the bug!** Active notification lock was never cleared.

**Fixed in this update:** Lock now auto-clears after 10 seconds.

---

## Testing

### Test Active Notification Lock

```bash
./venv/bin/python dev_runner.py --diagnostics
```

**Steps:**
1. Slouch → First nudge at T=0
2. Stay slouched → Should see dedupe suppression
3. Switch to forward lean → Should nudge at T=11s (after lock clears)

**Expected logs:**
```
21:00:00 - nudged (slouch)
21:00:05 - suppressed (slouch, active_notification_exists)
21:00:11 - nudged (forward_lean)  ← Lock cleared!
```

### Test Per-State De-dupe

```bash
./venv/bin/python dev_runner.py
```

**Steps:**
1. Slouch → Nudge at T=0
2. Fix posture for 30s
3. Slouch again at T=60s → Should nudge (dedupe expired after 20m)

---

## Summary

**M1 Timing Rules:**
- **10 seconds:** Active notification lock (auto-clear)
- **20 minutes:** Per-state dedupe window
- **Different states:** Can nudge every 10+ seconds

**Configuration:** All values adjustable in `NudgeConfig`

**Fix Applied:** Active notification lock now auto-clears after 10 seconds

**Test:** Slouch → wait 15s → forward lean → should get 2 nudges

---

**Notification Timing: COMPLETE ✅**
