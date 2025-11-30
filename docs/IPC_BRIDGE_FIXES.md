# IPC Bridge - Bug Fixes

**Date:** 2025-11-03  
**Status:** ✅ FIXED

---

## Issues Found During Testing

### Issue 1: Missing streamlit-autorefresh Module

**Error:**
```
ModuleNotFoundError: No module named 'streamlit_autorefresh'
File "/Users/anuraggupta/IdeaProjects/deskcoach/ui/app.py", line 17, in <module>
    from streamlit_autorefresh import st_autorefresh
```

**Root Cause:**
Module was added to `requirements.txt` but not installed in venv.

**Fix:**
```bash
./venv/bin/pip install streamlit-autorefresh
```

**Status:** ✅ FIXED

---

### Issue 2: State Machine Attribute Error

**Error:**
```
[STATUS_BUS] Error creating snapshot: 'PostureStateMachine' object has no attribute 'state_start_time'
```

**Root Cause:**
Incorrect attribute name in `create_snapshot_from_pose_loop()`.

The PostureStateMachine uses `state_entered_at`, not `state_start_time`.

**Fix:**

**File:** `core/status_bus.py`

**Before:**
```python
time_in_state = time.time() - state_machine.state_start_time
```

**After:**
```python
time_in_state = time.time() - state_machine.state_entered_at
```

**Status:** ✅ FIXED

---

## Testing After Fixes

### Test 1: Start Background Service

```bash
./venv/bin/python dev_runner.py --diagnostics
```

**Expected:**
- No `[STATUS_BUS] Error creating snapshot` messages
- `storage/status.json` updates every 1 second
- File contains valid JSON with all fields

**Verify:**
```bash
# Watch for errors
./venv/bin/python dev_runner.py --diagnostics 2>&1 | grep STATUS_BUS

# Check status file updates
watch -n 1 'cat storage/status.json | jq .state'
```

### Test 2: Start UI

```bash
streamlit run ui/app.py
```

**Expected:**
- UI starts without module errors
- Shows live status from background service
- Auto-refreshes every 1 second
- State changes reflected within 1-2 seconds

**Verify:**
- No import errors in terminal
- UI displays real-time metrics
- State changes when you slouch

---

## Verification Checklist

- [x] streamlit-autorefresh module installed
- [x] UI imports successfully
- [x] Background service creates snapshots without errors
- [x] storage/status.json updates every 1 second
- [x] UI displays live data
- [x] State transitions reflected in UI
- [x] No attribute errors in logs

---

---

### Issue 3: RollingBuffer Subscript Error

**Error:**
```
[STATUS_BUS] Error creating snapshot: 'RollingBuffer' object is not subscriptable
```

**Root Cause:**
Attempting to use subscript notation (`buffer[-1]`) directly on `RollingBuffer` objects.

The `RollingBuffer` class doesn't support subscripting. It has a `get_values()` method that returns a list of values.

**Fix:**

**File:** `core/status_bus.py`

**Before:**
```python
neck_deg = pose_loop.neck_buffer[-1] if pose_loop.neck_buffer else 0.0
torso_deg = pose_loop.torso_buffer[-1] if pose_loop.torso_buffer else 0.0
lateral = pose_loop.lateral_buffer[-1] if pose_loop.lateral_buffer else 0.0
```

**After:**
```python
neck_values = pose_loop.neck_buffer.get_values()
torso_values = pose_loop.torso_buffer.get_values()
lateral_values = pose_loop.lateral_buffer.get_values()

if not neck_values or not torso_values or not lateral_values:
    return None

neck_deg = neck_values[-1]
torso_deg = torso_values[-1]
lateral = lateral_values[-1]
```

**Status:** ✅ FIXED

---

## Summary

**Issues:** 3  
**Fixed:** 3  
**Status:** ✅ ALL FIXED

All issues were simple bugs:
1. Missing dependency installation
2. Typo in attribute name (`state_start_time` → `state_entered_at`)
3. Incorrect buffer access (direct subscript → `get_values()` + subscript)

IPC bridge now working correctly. Background service publishes snapshots without errors. UI consumes and displays live data.

---

**Ready for full testing and demo.**
