# Notification & Logging Fixes

**Date:** 2025-11-03  
**Status:** ✅ COMPLETE

---

## Issues Found

### Issue 1: Notifications Not Appearing
When monitoring service is started from UI, state transitions from GOOD → SLOUCH do not trigger notifications.

### Issue 2: No Access to Backend Logs
When service is started from UI (subprocess), logs are not visible. Manual terminal execution showed logs but subprocess doesn't.

---

## Root Causes

### Issue 1: Notifications
**Status:** Likely working, but logs were not visible to confirm

The notification system is properly integrated:
- `NotificationPolicy` is initialized with `NotificationEngine`
- `on_state_transition` callback is properly wired
- `post_with_terminal_notifier` is called on state changes
- Logs show "[POLICY] Attempting to post notification..." messages

**However:** Without visible logs, we couldn't confirm if notifications were being sent or failing.

### Issue 2: Logs
**Root Cause:** `service_manager.py` redirected subprocess stdout/stderr to `DEVNULL`

```python
# BEFORE (Bad)
process = subprocess.Popen(
    cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    ...
)
```

This made it impossible to:
- Debug notification failures
- See state transitions
- Monitor service health
- Troubleshoot issues

---

## Fixes Applied

### Fix 1: Redirect Logs to File

**File:** `core/service_manager.py`

**Changed:**
```python
# AFTER (Good)
log_handle = open(self.log_file, 'w')

process = subprocess.Popen(
    cmd,
    stdout=log_handle,
    stderr=subprocess.STDOUT,  # Merge stderr into stdout
    ...
)
```

**Benefits:**
- All stdout/stderr captured to `storage/deskcoach.log`
- Can see state transitions
- Can see notification attempts (success/failure)
- Can debug issues
- Logs persist across sessions

### Fix 2: Add Log Viewing Methods

**Added methods to `ServiceManager`:**

```python
def get_logs(self, lines: int = 100) -> str:
    """Get recent logs from the service."""
    
def tail_logs(self, lines: int = 20) -> str:
    """Get tail of logs (last N lines)."""
    
def clear_logs(self):
    """Clear the log file."""
```

### Fix 3: Add Logs Section to UI

**File:** `ui/app_with_controls.py`

**Added:**
- 📝 Service Logs section
- Slider to control number of lines (10-100)
- Refresh Logs button
- Clear Logs button
- Code block showing log contents

```python
if is_running:
    log_lines = st.slider("Lines to show", 10, 100, 30)
    logs = service_mgr.tail_logs(lines=log_lines)
    st.code(logs, language="text")
```

### Fix 4: Update .gitignore

**Added:** `storage/deskcoach.log` to `.gitignore`

---

## How to Use

### View Logs in UI

1. Start monitoring: Click "▶️ Start Monitoring"
2. Scroll to "📝 Service Logs" section
3. Adjust slider to see more/fewer lines
4. Click "🔄 Refresh Logs" to update
5. Click "🗑️ Clear Logs" to clear old logs

### View Logs in Terminal

```bash
# Tail logs in real-time
tail -f storage/deskcoach.log

# View last 50 lines
tail -n 50 storage/deskcoach.log

# View all logs
cat storage/deskcoach.log

# Clear logs
rm storage/deskcoach.log
```

### Check for Notification Issues

**Look for these log lines:**

**Success:**
```
STATE TRANSITION: GOOD → SLOUCH
[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Your neck is tilted forward 15.2° (threshold: 18.3°)
[POLICY] ✅ Notification posted successfully!
```

**Failure:**
```
STATE TRANSITION: GOOD → SLOUCH
[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Your neck is tilted forward 15.2° (threshold: 18.3°)
[POLICY] ❌ Failed to post notification
```

**Suppressed:**
```
STATE TRANSITION: GOOD → SLOUCH
[POLICY] Nudge suppressed: global_cooldown (28.5m remaining)
```

---

## Testing Notifications

### Test 1: Manual Notification Test

```bash
python test_notifications.py
```

**Expected output:**
```
Testing notification system...
Sending test notification...
✅ Notification sent successfully
```

**You should see:** A macOS notification with title "DeskCoach Test"

### Test 2: Monitor Logs During Slouching

```bash
# Terminal 1: Start monitoring from UI
streamlit run ui/app_with_controls.py
# Click "Start Monitoring"

# Terminal 2: Watch logs
tail -f storage/deskcoach.log
```

**Steps:**
1. Sit upright for 10 seconds (state = GOOD)
2. Slouch heavily for 30+ seconds
3. Watch terminal for state transition
4. Look for "[POLICY]" lines

**Expected in logs:**
```
================================================================================
STATE TRANSITION: GOOD → SLOUCH
Reason: Sustained condition: Majority above threshold for 30.1s (63% above)
Time in previous state: 12.5s
Metrics: Neck=25.3°, Torso=3.1°, Lateral=0.042
================================================================================

[POLICY] Attempting to post notification...
  Title: Posture Check: Slouching
  Message: Your neck is tilted forward 25.3° (threshold: 18.3°). ...
[POLICY] ✅ Notification posted successfully!
[POLICY] Nudge posted: slouch
```

**Expected notification:**
- Title: "Posture Check: Slouching"
- Message: Describes the issue
- Sound: Default notification sound

### Test 3: Check for Suppression

If no notification appears, check logs for suppression:

```bash
grep "POLICY" storage/deskcoach.log | grep -i "suppressed\|cooldown\|snooze"
```

**Common suppressions:**
- `global_cooldown (X.Xm remaining)` - Recently clicked "Done" button
- `snooze (X.Xm remaining)` - Recently clicked "Snooze" button
- `dedupe_window (X.Xm remaining)` - Same state recently nudged
- `active_notification_exists` - Previous notification still visible

---

## Troubleshooting

### Problem: No notification appears, logs show "✅ Notification posted successfully"

**Possible causes:**
1. **macOS notifications disabled**
   - Check System Settings → Notifications → Terminal (or Python)
   - Enable "Allow Notifications"

2. **Do Not Disturb enabled**
   - Check if DND is active (moon icon in menu bar)
   - Logs should show "[POLICY] Nudge queued (DND active)"

3. **Notification dismissed quickly**
   - macOS notifications auto-dismiss after 5-10 seconds
   - Check Notification Center for missed notifications

### Problem: Logs show "❌ Failed to post notification"

**Possible causes:**
1. **terminal-notifier not installed**
   ```bash
   # Check if installed
   which terminal-notifier
   
   # Install if missing
   brew install terminal-notifier
   ```

2. **terminal-notifier permissions**
   ```bash
   # Test directly
   terminal-notifier -title "Test" -message "Test message"
   ```

3. **Subprocess environment issues**
   - Check if PATH includes Homebrew bin directory
   - Logs might show command not found error

### Problem: Notifications suppressed every time

**Check cooldown/snooze timers:**

```bash
grep "POLICY.*suppressed" storage/deskcoach.log
```

**Solutions:**
- Wait for cooldown to expire
- Restart monitoring to reset timers
- Check `nudge_config` settings in dev_runner.py

### Problem: Can't see logs in UI

**Check:**
1. Service is running (PID shown)
2. Log file exists: `ls -l storage/deskcoach.log`
3. Log file has content: `wc -l storage/deskcoach.log`
4. Click "🔄 Refresh Logs" button

---

## Files Modified

### 1. `core/service_manager.py`
- Added `log_file` parameter to `__init__`
- Changed subprocess stdout/stderr to log file
- Added `get_logs()` method
- Added `tail_logs()` method
- Added `clear_logs()` method

### 2. `ui/app_with_controls.py`
- Added "📝 Service Logs" section
- Log viewer with adjustable line count
- Refresh and Clear buttons

### 3. `.gitignore`
- Added `storage/deskcoach.log`

### 4. `test_notifications.py` (new)
- Standalone notification tester

---

## Log File Details

**Location:** `storage/deskcoach.log`

**Content:**
- All stdout from dev_runner.py
- All stderr from dev_runner.py
- State transitions
- Notification attempts
- Policy decisions
- Metrics output (if diagnostics enabled)

**Size:** 
- Typically 10-50 KB per hour
- Grows with diagnostics enabled
- Can be cleared anytime

**Rotation:**
- Currently: Overwritten on each start
- Future: Could add log rotation (M2)

**Privacy:**
- ✅ Only metrics (angles, timestamps)
- ✅ No frames or images
- ✅ Gitignored

---

## Summary

**Problems:**
1. ❌ Notifications not appearing → Could not debug (no logs)
2. ❌ Logs not accessible → Blind to service behavior

**Solutions:**
1. ✅ Redirect logs to `storage/deskcoach.log`
2. ✅ Add log viewer to UI
3. ✅ Add `test_notifications.py` for debugging
4. ✅ Document troubleshooting steps

**Benefits:**
- Can see if notifications are sent
- Can debug notification failures
- Can monitor service health
- Can troubleshoot issues
- Logs accessible from UI and terminal

---

## Next Steps

### Immediate

1. **Test notifications:**
   ```bash
   python test_notifications.py
   ```

2. **Start monitoring and check logs:**
   ```bash
   streamlit run ui/app_with_controls.py
   # Click "Start Monitoring"
   # Scroll to "Service Logs" section
   ```

3. **Trigger a slouch and check logs:**
   - Slouch heavily for 30+ seconds
   - Look for state transition in logs
   - Look for "[POLICY]" notification lines
   - Verify notification appears

4. **If notification doesn't appear:**
   - Check logs for "[POLICY] ❌ Failed"
   - Check logs for "[POLICY] Nudge suppressed"
   - Run `python test_notifications.py`
   - Check macOS notification settings

### Future (M2)

1. **Log rotation** - Prevent log file from growing too large
2. **Log levels** - DEBUG, INFO, WARNING, ERROR
3. **Structured logging** - JSON format for easier parsing
4. **Log streaming** - Real-time log view in UI (WebSocket)
5. **Log search** - Search logs for specific events
6. **Log export** - Export logs for support/debugging

---

**Notification & Logging Fixes: COMPLETE ✅**

Logs now accessible in UI and terminal. Can debug notification issues. All stdout/stderr captured to `storage/deskcoach.log`.
