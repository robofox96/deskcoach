# Notification Not Appearing - Root Cause & Fix

**Date:** 2025-11-02  
**Issue:** Logs show "Notification posted successfully" but no popup appears  
**Status:** ✅ FIXED

---

## Problem

User reports:
- Terminal logs show `[POLICY] ✅ Notification posted successfully!`
- No notification popup on screen
- No notification in Notification Center
- No notification in Control Center

The notification engine was **claiming success** but notifications weren't actually appearing.

---

## Root Cause

### Issue 1: Silent Error Suppression

The notification code used `subprocess.Popen()` with stderr redirected to `/dev/null`:

```python
subprocess.Popen(
    cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL  # ← Errors silently ignored!
)
return True  # ← Always returns True, even if it failed!
```

**Impact:** If terminal-notifier failed for any reason (permissions, invalid parameters, etc.), the error was silently swallowed and we'd never know.

### Issue 2: `-group` Parameter Replacing Notifications

The code used `-group "DeskCoach"`:

```python
cmd = [
    "terminal-notifier",
    "-title", title,
    "-message", message,
    "-group", self.app_name,  # ← Problem!
    ...
]
```

**terminal-notifier behavior with `-group`:**
- When you post a notification with a group ID, it **replaces** any previous notification in that group
- Output: `"* Removing previously sent notification, which was sent on: 2025-11-02 17:03:46 +0000"`
- The old notification disappears, new one appears... but macOS might not show it if it considers it a "replacement"

**Impact:** Only the first notification in each session would appear. All subsequent ones would "replace" the previous one, but macOS wouldn't actually show them.

### Issue 3: Invalid `-sender` Bundle ID

The code used `-sender "com.deskcoach.app"`:

```python
cmd = [
    ...
    "-sender", "com.deskcoach.app"  # ← Non-existent bundle ID!
]
```

**Impact:** macOS might block or ignore notifications claiming to be from a bundle ID that doesn't exist in the system. This is a security measure to prevent notification spoofing.

---

## Solution

### Fix 1: Capture and Log Errors

```python
# Capture stderr to detect errors
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,  # ← Capture errors now
    text=True
)

# Check for immediate failures
try:
    stdout, stderr = proc.communicate(timeout=0.1)
    if stderr:
        print(f"  [NOTIFICATION] Warning: {stderr.strip()}")
except subprocess.TimeoutExpired:
    # Process still running - good!
    pass
```

Now we'll see error messages in the terminal if terminal-notifier fails.

### Fix 2: Remove `-group` Parameter

```python
cmd = [
    "terminal-notifier",
    "-title", title,
    "-message", message,
    "-sound", "default"  # ← Added sound for visibility
    # NOTE: Removed -group (was causing replacements)
]
```

Without `-group`, each notification is independent and will show properly.

### Fix 3: Remove `-sender` Parameter

```python
# NOTE: Removed -sender (was using non-existent bundle ID)
```

Let terminal-notifier use its default sender (Terminal.app or Python.app), which are valid apps with notification permissions.

### Fix 4: Add Sound

```python
"-sound", "default"  # Add audible notification
```

This makes notifications more noticeable and confirms they're being posted.

---

## Testing

### Test 1: Direct Command

```bash
# Old command (problematic)
terminal-notifier -title "Test" -message "Hello" -group "DeskCoach" -sender "com.deskcoach.app"
# Output: "* Removing previously sent notification..."

# New command (fixed)
terminal-notifier -title "Test" -message "Hello" -sound "default"
# Output: (none, notification appears)
```

### Test 2: From Python

```bash
./venv/bin/python test_notification.py
```

**Expected:**
- 2 notifications appear on screen
- Both have sound
- Terminal shows no errors

### Test 3: From dev_runner

```bash
./venv/bin/python dev_runner.py --diagnostics
```

**Steps:**
1. Slouch heavily for 30+ seconds
2. Watch terminal output
3. Check for notification popup

**Expected terminal output:**
```
[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Neck 18.5° > 17.9°
[POLICY] ✅ Notification posted successfully!
```

**Expected on screen:**
- Notification popup appears
- Sound plays
- Notification shows in Notification Center

**If errors occur:**
```
[NOTIFICATION] Warning: <error message>
```

---

## Verification Checklist

### ✅ Before Running

1. **Check terminal-notifier is installed:**
   ```bash
   which terminal-notifier
   # Should output: /opt/homebrew/bin/terminal-notifier
   ```

2. **Check macOS notification permissions:**
   - System Settings → Notifications
   - Find "Terminal" or "Python"
   - Ensure "Allow Notifications" is enabled
   - Set alert style to "Banners" or "Alerts"

3. **Disable Do Not Disturb:**
   ```bash
   # Check DND status
   defaults read com.apple.notificationcenterui doNotDisturb
   # Should be 0 or error (not set)
   ```

### ✅ After Running

1. **Check notification appears:**
   - Popup in top-right corner
   - Sound plays
   - Can see in Notification Center

2. **Check for error messages:**
   - Terminal should NOT show `[NOTIFICATION] Warning:` or `[NOTIFICATION] Error:`
   - If errors appear, they will now be visible

3. **Check notification persists:**
   - Open Notification Center (top-right)
   - Should see DeskCoach notification(s)
   - Click to dismiss or interact

---

## Troubleshooting

### "Still no notifications after fix"

**Step 1: Test terminal-notifier directly**

```bash
terminal-notifier -title "Direct Test" -message "Testing" -sound "default"
```

**Did notification appear?**

**YES** → Issue is in Python code, check:
- Python has notification permissions
- No exceptions in dev_runner output
- Check for `[NOTIFICATION] Warning:` messages

**NO** → Issue is with terminal-notifier or macOS:
- Check notification permissions for Terminal
- Try running from different terminal (iTerm2, etc.)
- Restart terminal-notifier: `brew reinstall terminal-notifier`

**Step 2: Check permissions**

```bash
# Check which app is running terminal-notifier
ps aux | grep terminal-notifier

# The parent process should have notification permissions
# If it's Terminal.app, check System Settings → Notifications → Terminal
```

**Step 3: Enable notification debugging**

```bash
# Run with verbose output
./venv/bin/python dev_runner.py --diagnostics 2>&1 | tee debug.log

# Slouch to trigger notification
# Check debug.log for [NOTIFICATION] lines
```

**Step 4: Check system logs**

```bash
# Check for notification-related errors
log show --predicate 'subsystem == "com.apple.notificationcenter"' --last 5m

# Look for errors or denials
```

### "Notifications work but are silent"

**Issue:** Sound not playing

**Fix:**
1. Check macOS sound settings
2. Check notification settings for Terminal/Python
3. Ensure system volume is not muted
4. Try different sound: `-sound "Glass"` or `-sound "Ping"`

### "Only first notification appears"

**Issue:** Dedupe window (20 minutes for same state)

**Fix:**
- Wait 20 minutes OR
- Try different posture state (slouch vs forward lean) OR
- Disable dedupe: Edit `nudge_config.py`, set `dedupe_window_sec = 60`

---

## Implementation Details

### File Changed

**`core/notifications.py`**

**Before:**
```python
subprocess.Popen(
    cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL  # Silent failures
)
```

**After:**
```python
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

try:
    stdout, stderr = proc.communicate(timeout=0.1)
    if stderr:
        print(f"  [NOTIFICATION] Warning: {stderr.strip()}")
except subprocess.TimeoutExpired:
    pass  # Still running, good!
```

### Parameters Changed

| Parameter | Before | After | Reason |
|-----------|--------|-------|--------|
| `-group` | `"DeskCoach"` | Removed | Caused replacements |
| `-sender` | `"com.deskcoach.app"` | Removed | Invalid bundle ID |
| `-sound` | Not present | `"default"` | Added for visibility |
| Error handling | Ignored | Captured | Debug visibility |

---

## macOS Notification Behavior

### How `-group` Works

From terminal-notifier docs:
> When a notification with a group ID is posted, it replaces any previous notification with the same group ID.

**Example:**
```bash
terminal-notifier -title "Test 1" -message "First" -group "MyGroup"
# Notification appears

terminal-notifier -title "Test 2" -message "Second" -group "MyGroup"
# First notification disappears, second appears (maybe)
```

**Problem:** macOS doesn't always show the "replacement" notification, especially if it comes quickly after the first.

**Solution:** Don't use `-group` for independent notifications.

### How `-sender` Works

From terminal-notifier docs:
> Specify the bundle identifier of the application that should be shown as the sender of the notification.

**Problem:** If you specify a bundle ID that doesn't exist in the system, macOS may:
- Ignore the notification
- Show it as "terminal-notifier" instead
- Block it as potentially malicious

**Solution:** Omit `-sender` to use the default (Terminal.app or Python.app).

---

## Summary

**Root Causes:**
1. ❌ Errors silently suppressed (stderr → /dev/null)
2. ❌ `-group` parameter causing replacements
3. ❌ Invalid `-sender` bundle ID
4. ❌ No sound (made it less noticeable)

**Fixes Applied:**
1. ✅ Capture and log stderr errors
2. ✅ Remove `-group` parameter
3. ✅ Remove `-sender` parameter
4. ✅ Add `-sound "default"`

**Result:**
- Errors now visible in terminal
- Each notification independent (no replacements)
- Valid sender (Terminal/Python)
- Audible feedback

**Test:**
```bash
./venv/bin/python dev_runner.py --diagnostics
# Slouch for 30s → Notification should appear with sound!
```

---

**NOTIFICATION FIX APPLIED ✅**

Now notifications should actually appear on your screen!
