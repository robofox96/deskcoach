# DeskCoach UI - Streamlit Interface

## Overview

Minimal single-page Streamlit UI for DeskCoach v1 that provides:
- Live status display (state, metrics, FPS, policy timers)
- Sensitivity configuration (presets, thresholds, detection windows)
- Notification policy settings (cooldowns, backoff, DND)
- System controls (start/stop, camera, FPS)
- Calibration management
- Privacy controls (pause, purge)
- Today's stats (nudges, actions)
- Event log viewer

**PRIVACY:** No camera frames are ever displayed or saved. Only posture metrics (angles, timestamps) are shown.

---

## Installation

### Prerequisites

1. Python 3.11 or 3.12 (MediaPipe doesn't support 3.13 yet)
2. Virtual environment activated
3. Dependencies installed

### Install Streamlit

```bash
# Activate virtual environment
source venv/bin/activate

# Install Streamlit
pip install streamlit>=1.30.0

# Verify installation
streamlit --version
```

---

## Running the UI

### Start the UI

```bash
# From project root
streamlit run ui/app.py

# Or with custom port
streamlit run ui/app.py --server.port 8502
```

The UI will open in your default browser at `http://localhost:8501`

### Run with Background Service

For full functionality, run the background pose loop in a separate terminal:

```bash
# Terminal 1: Start background service
python dev_runner.py --diagnostics

# Terminal 2: Start UI
streamlit run ui/app.py
```

---

## UI Sections

### 1. Live Status
- **Current State:** GOOD, SLOUCH, FORWARD_LEAN, LATERAL_LEAN, or PAUSED
- **Time in State:** How long in current state
- **Confidence:** Pose detection confidence (0.0-1.0)
- **FPS:** Actual frames per second
- **Current Metrics:** Neck flexion, torso flexion, lateral lean with thresholds
- **Policy Status:** Active cooldowns, snooze, backoff, last nudge time

**Note:** Live status requires IPC integration with background service (coming in future update). Currently shows mock data for UI preview.

### 2. Sensitivity Configuration
- **Preset Selector:** Quick presets (Sensitive/Standard/Conservative)
- **Threshold Sliders:**
  - Neck slouch (degrees above baseline)
  - Torso forward lean (degrees above baseline)
  - Lateral lean (centimeters of shoulder asymmetry)
- **Advanced Settings** (expandable):
  - Window duration (seconds)
  - Majority fraction (0.5-0.9)
  - Gap budget (seconds)
  - Cumulative minimum (seconds)
  - High-severity delta and window

**Changes apply immediately** and persist to `storage/ui_config.json`

### 3. Notification Policy
- **Cooldowns:**
  - Done cooldown (5-60 minutes)
  - Snooze duration (5-30 minutes)
- **Dismiss Backoff:**
  - Neck backoff (degrees)
  - Torso backoff (degrees)
  - Lateral backoff (cm)
  - Backoff duration (15-120 minutes)
- **Other Settings:**
  - De-dupe window (5-30 minutes)
  - Respect Do Not Disturb (checkbox)
  - DND queue expiry (15-90 minutes)
  - High-severity bypass de-dupe (checkbox)

**Changes apply immediately** and persist to config

### 4. System Controls
- **Start/Stop Monitoring:** Toggle background service (requires integration)
- **Camera Index:** Select which camera to use (0 = default)
- **Target FPS:** 5-15 FPS (higher = more responsive, more CPU)
- **Diagnostics:** Enable detailed window stats
- **Smoothing (EMA Alpha):** 0.1-0.5 (lower = more smoothing)
- **Metrics Window:** 30-120 seconds rolling window

### 5. Calibration
- **Status:** Shows last calibration timestamp and baselines
- **Baselines:** Neck, torso, lateral baseline values
- **Recalibrate Button:** Prompts to run `python dev_runner_calibrate.py`

**Note:** UI-integrated calibration flow coming in future update

### 6. Privacy Controls
- **Privacy Notice:** Prominent reminder that no frames are saved
- **Pause Monitoring:** Temporarily pause pose detection
- **Purge Data:** Delete all logs, events, and configuration
  - Requires confirmation
  - Deletes: event logs, config settings
  - Optional: calibration data

### 7. Today's Stats
- **Total Nudges:** Count of nudges today
- **Action Counts:** Done, Snooze, Dismiss actions
- **Nudges by State:** Slouch, Forward Lean, Lateral Lean
- **Last Nudge:** Time since last nudge

### 8. Event Log
- **Recent Events:** Last 100 events from `storage/events.jsonl`
- **Filters:** By event type and state
- **Display:** Timestamp, event type, state, reason
- **Export:** CSV export button (coming soon)

---

## Configuration Persistence

### What is Persisted

**File:** `storage/ui_config.json`

**Contents:**
- State configuration (preset, thresholds, policies)
- Nudge configuration (cooldowns, backoff, dedupe)
- System configuration (FPS, camera, diagnostics)

**When:**
- Automatically saved when clicking "Save" buttons
- Loaded on UI startup
- Applied immediately (no restart needed)

### What is In-Memory Only

- Live status (state, metrics, FPS)
- Policy timers (cooldown remaining, snooze remaining)
- Active notification state
- UI session state (expanded sections, etc.)

---

## Integration with Background Service

### Current Status (M1)

The UI is **self-contained** and can run independently. However, for full functionality:

**Implemented:**
- Configuration management (load/save)
- Calibration status display
- Event log viewing
- Stats aggregation

**Requires Integration:**
- Live status updates (IPC/shared memory)
- Start/stop monitoring control
- Real-time metrics display
- Policy timer updates

### Future Integration (M2)

Options for background service communication:
1. **Shared Memory:** Fast, low overhead
2. **Unix Socket:** Simple IPC
3. **File-based:** Polling `storage/status.json`
4. **Redis/SQLite:** More robust, higher overhead

**Recommended:** File-based polling for M1 simplicity, upgrade to shared memory for M2.

---

## Development

### File Structure

```
ui/
├── __init__.py              # Module init
├── app.py                   # Main Streamlit app
├── config_manager.py        # Config persistence
├── README_UI.md            # This file
└── pages/                   # (Future) Modular page components
    ├── __init__.py
    ├── status.py
    ├── sensitivity.py
    ├── policy.py
    ├── system.py
    ├── calibration.py
    ├── privacy.py
    ├── stats.py
    └── events.py
```

### Adding New Features

1. **New Config Parameter:**
   - Add to `config_manager.py` default config
   - Add UI control in appropriate section
   - Save/load in config methods

2. **New Stat:**
   - Query from `event_logger.get_recent_events()`
   - Aggregate and display in stats section

3. **New Event Type:**
   - Log in `core/event_logger.py`
   - Display in event log section
   - Add to filters if needed

### Debugging

```bash
# Run with debug logging
streamlit run ui/app.py --logger.level=debug

# Check config file
cat storage/ui_config.json | jq .

# Check event log
cat storage/events.jsonl | tail -20 | jq .

# Clear Streamlit cache
streamlit cache clear
```

---

## Troubleshooting

### UI Won't Start

**Error:** `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
source venv/bin/activate
pip install streamlit>=1.30.0
```

### Config Not Saving

**Error:** Settings revert after restart

**Solution:**
- Check `storage/` directory exists and is writable
- Check `storage/ui_config.json` permissions
- Look for errors in terminal output

### Live Status Not Updating

**Expected:** Live status shows mock data in M1

**Solution:**
- This is expected behavior
- Integration with background service coming in M2
- For now, run `dev_runner.py` separately to see live metrics in terminal

### Calibration Not Found

**Error:** "Not calibrated" message

**Solution:**
```bash
python dev_runner_calibrate.py
```

Follow prompts to calibrate, then refresh UI

---

## Privacy & Security

### Data Stored

**Local Only:**
- `storage/ui_config.json` - Configuration settings
- `storage/events.jsonl` - Event log (metrics only, no frames)
- `storage/calibration.json` - Baseline values

**Never Stored:**
- Camera frames or video
- Screenshots or images
- Personal identifying information

### Purge Data

The "Purge Data" button deletes:
1. All event logs (`storage/events.jsonl`)
2. All configuration (`storage/ui_config.json`)
3. Optionally: calibration data

**Note:** Purge is immediate and cannot be undone.

### Network Access

**None.** The UI runs entirely locally:
- No external API calls
- No telemetry or analytics
- No cloud sync
- All data stays on your machine

---

## Performance

### Resource Usage

**Typical:**
- CPU: <5% (Streamlit overhead)
- Memory: ~100MB (Streamlit + Python)
- Disk: <1MB (config + logs)

**Note:** Background pose loop uses additional ~15% CPU

### Optimization Tips

1. **Lower FPS:** Reduce target FPS to 6-7 for lower CPU
2. **Disable Diagnostics:** Turn off diagnostics when not needed
3. **Clear Old Logs:** Periodically purge old event logs
4. **Close Unused Tabs:** Streamlit uses resources per browser tab

---

## Known Limitations

1. **Live Status:** Requires IPC integration (mock data for now)
2. **Start/Stop Control:** Requires background service integration
3. **Calibration Flow:** Must run CLI tool, not integrated in UI
4. **Export CSV:** Event log export not yet implemented
5. **Multi-page:** Single page for M1, multi-page for M2

---

## Next Steps

### M2 Features

- [ ] IPC integration for live status
- [ ] Start/stop monitoring from UI
- [ ] UI-integrated calibration flow
- [ ] Event log CSV export
- [ ] Weekly stats and charts
- [ ] Multi-page layout
- [ ] Dark mode theme
- [ ] Keyboard shortcuts

### Packaging

- [ ] Bundle UI with background service
- [ ] System tray integration
- [ ] Auto-start on login
- [ ] macOS app bundle
- [ ] Windows installer

---

## Support

For issues or questions:
1. Check this README
2. Check `docs/` directory for detailed docs
3. Run with `--logger.level=debug` for detailed logs
4. Check `storage/events.jsonl` for event history

---

**DeskCoach UI v1 - Privacy-first posture monitoring**
