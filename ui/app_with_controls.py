"""
DeskCoach Streamlit UI - With Start/Stop and Calibration Controls
PRIVACY: No frames displayed or saved, only metrics.
"""
import streamlit as st
import time
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import sys
import os

# In frozen app, sys.path is already set up by entry_launcher
# Only add parent.parent in development mode
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (CalibrationStorage, StateConfig, NudgeConfig, SensitivityPreset, EventLogger,
                  get_service_manager, get_calibration_runner, read_calibration_status,
                  CalibrationStatusPublisher, get_login_item_status, toggle_login_item)
from ui.config_manager import ConfigManager
from streamlit_autorefresh import st_autorefresh

# Page config
st.set_page_config(page_title="DeskCoach", page_icon="🪑", layout="wide")

# CSS
st.markdown("""
<style>
.status-good { color: #28a745; font-weight: bold; }
.status-issue { color: #dc3545; font-weight: bold; }
.status-paused { color: #6c757d; font-weight: bold; }
.privacy-notice {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
    padding: 1rem;
    border-radius: 0.5rem;
}
.waiting-banner {
    background-color: #fff3cd;
    border: 1px solid #ffc107;
    color: #856404;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'config_manager' not in st.session_state:
    st.session_state.config_manager = ConfigManager()
if 'calibration_storage' not in st.session_state:
    st.session_state.calibration_storage = CalibrationStorage()
if 'event_logger' not in st.session_state:
    st.session_state.event_logger = EventLogger()

# Get managers
service_mgr = get_service_manager()
cal_runner = get_calibration_runner()

# Check status
is_running = service_mgr.is_running()
is_calibrating = cal_runner.is_calibrating()
cal_status = read_calibration_status()

# Auto-refresh logic
if is_calibrating:
    # Fast refresh during calibration
    st_autorefresh(interval=250, key="cal_refresh")
elif is_running:
    # Normal refresh when monitoring
    st_autorefresh(interval=1000, key="monitor_refresh")

st.title("🪑 DeskCoach")
st.caption("Privacy-first posture monitoring - No frames saved")

# System Controls
st.header("🎮 System Controls")

col1, col2 = st.columns(2)

with col1:
    if is_running:
        pid = service_mgr.get_pid()
        st.success(f"✅ Monitoring: Running (PID: {pid})")
    else:
        st.info("⏸ Monitoring: Stopped")

with col2:
    if is_calibrating:
        pid = cal_runner.get_pid()
        st.warning(f"🔄 Calibration: In Progress (PID: {pid})")
    else:
        st.info("✓ Calibration: Idle")

# Control buttons
col1, col2, col3 = st.columns(3)

with col1:
    start_disabled = is_running or is_calibrating
    if st.button("▶️ Start Monitoring", disabled=start_disabled, key="start_btn"):
        config = st.session_state.config_manager.load_config()
        pid = service_mgr.start_background(
            camera_index=config['system_config'].get('camera_index', 0),
            target_fps=config['system_config'].get('target_fps', 8.0),
            diagnostics=config['system_config'].get('diagnostics', True),
            preset=config['state_config'].get('preset', 'sensitive')
        )
        if pid:
            st.success(f"Started (PID: {pid})")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Failed to start")

with col2:
    stop_disabled = not is_running
    if st.button("⏹ Stop Monitoring", disabled=stop_disabled, key="stop_btn"):
        if service_mgr.stop_background():
            st.success("Stopped")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Failed to stop")

with col3:
    restart_disabled = not is_running or is_calibrating
    if st.button("🔄 Restart", disabled=restart_disabled, key="restart_btn"):
        if service_mgr.stop_background():
            time.sleep(1)
            service_info = service_mgr.get_service_info()
            if service_info:
                pid = service_mgr.start_background(
                    camera_index=service_info['camera_index'],
                    target_fps=service_info['target_fps'],
                    diagnostics=service_info['diagnostics'],
                    preset=service_info['preset']
                )
                if pid:
                    st.success(f"Restarted (PID: {pid})")
                    st.rerun()

st.divider()

# Load live status
def load_live_status():
    status_file = Path("storage/status.json")
    if not status_file.exists():
        return None, "File not found"
    try:
        mtime = status_file.stat().st_mtime
        age = time.time() - mtime
        if age > 3.0:
            return None, f"Stale ({age:.1f}s old)"
        with open(status_file, 'r') as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)

status, error = load_live_status()

# Live Status Section
st.header("📊 Live Status")

if error:
    st.markdown(f"""
    <div class="waiting-banner">
        <strong>⏳ Waiting for background service...</strong><br>
        Reason: {error}<br><br>
        Click "Start Monitoring" above to begin.
    </div>
    """, unsafe_allow_html=True)
else:
    state = status['state']
    if state == 'good':
        st.markdown(f'<p class="status-good">● GOOD - Posture within thresholds</p>', unsafe_allow_html=True)
    elif state == 'paused':
        st.markdown(f'<p class="status-paused">⏸ PAUSED - Low confidence</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="status-issue">⚠ {state.upper().replace("_", " ")}</p>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Time in State", f"{status['time_in_state_sec']:.0f}s")
    with col2:
        st.metric("Confidence", f"{status['confidence']:.2f}")
    with col3:
        st.metric("FPS", f"{status['fps']:.1f}")
    with col4:
        st.metric("Preset", status['preset'].upper())
    
    # Current metrics
    st.subheader("Current Metrics")
    col1, col2, col3 = st.columns(3)
    
    metrics = status['metrics']
    thresholds = status['thresholds']
    
    with col1:
        neck = metrics['neck_deg']
        neck_thresh = thresholds['neck_abs_deg']
        delta = neck - neck_thresh
        st.metric("Neck Flexion", f"{neck:.1f}°", delta=f"{delta:+.1f}°", delta_color="inverse")
    
    with col2:
        torso = metrics['torso_deg']
        torso_thresh = thresholds['torso_abs_deg']
        delta = torso - torso_thresh
        st.metric("Torso Flexion", f"{torso:.1f}°", delta=f"{delta:+.1f}°", delta_color="inverse")
    
    with col3:
        lateral = metrics['lateral']
        lateral_thresh = thresholds['lateral_abs']
        delta = lateral - lateral_thresh
        st.metric("Lateral Lean", f"{lateral:.3f}", delta=f"{delta:+.3f}", delta_color="inverse")

st.divider()

# Calibration Section
st.header("📏 Calibration")

# Prioritize terminal phases (done/error) over is_calibrating so the UI can exit
if cal_status and cal_status.phase == "done":
    st.success("✅ Calibration Complete!")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Neck", f"{cal_status.baseline_neck:.1f}°")
    with col2:
        st.metric("Torso", f"{cal_status.baseline_torso:.1f}°")
    with col3:
        st.metric("Lateral", f"{cal_status.baseline_lateral:.3f}")
    with col4:
        st.metric("Shoulder", f"{cal_status.baseline_shoulder_width:.3f}")
    
    if not is_running:
        if st.button("▶️ Start Monitoring", key="start_after_cal"):
            config = st.session_state.config_manager.load_config()
            pid = service_mgr.start_background(
                camera_index=config['system_config'].get('camera_index', 0),
                target_fps=config['system_config'].get('target_fps', 8.0),
                diagnostics=True,
                preset=config['state_config'].get('preset', 'sensitive')
            )
            if pid:
                st.success(f"Started (PID: {pid})")
                st.rerun()

    # After showing the completion state once, clear status so UI returns to normal view
    CalibrationStatusPublisher().clear()

elif cal_status and cal_status.phase == "error":
    st.error(f"❌ Calibration Failed: {cal_status.error_message}")
    if st.button("🔄 Try Again", key="retry_cal"):
        from core.calibration_status import CalibrationStatusPublisher
        CalibrationStatusPublisher().clear()
        st.rerun()

elif is_calibrating and cal_status:
    st.subheader("🔄 Calibration in Progress")
    
    progress = cal_status.progress_0_1
    st.progress(progress)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Phase", cal_status.phase.upper())
    with col2:
        st.metric("Elapsed", f"{cal_status.elapsed_sec:.1f}s")
    with col3:
        if cal_status.eta_sec is not None:
            st.metric("ETA", f"{cal_status.eta_sec:.1f}s")
    
    if cal_status.samples_captured > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Samples", cal_status.samples_captured)
        with col2:
            st.metric("Confidence", f"{cal_status.conf_mean:.2f}")
    
    if st.button("❌ Cancel Calibration", key="cancel_cal"):
        if cal_runner.stop_calibration():
            st.warning("Cancelled")
            st.rerun()

else:
    cal_info = st.session_state.calibration_storage.get_calibration_status()
    
    if cal_info['calibrated']:
        st.success(f"✅ Calibrated: {cal_info['calibrated_at']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Neck", f"{cal_info['neck_baseline']:.1f}°")
        col2.metric("Torso", f"{cal_info['torso_baseline']:.1f}°")
        col3.metric("Lateral", f"{cal_info['lateral_baseline']:.3f}")
    else:
        st.warning("⚠️ Not calibrated")
    
    col1, col2 = st.columns(2)
    with col1:
        cal_duration = st.slider("Duration (seconds)", 15, 45, 25, key="cal_duration")
    with col2:
        cal_camera = st.number_input("Camera Index", 0, 5, 0, key="cal_camera")
    
    recal_disabled = is_running or is_calibrating
    if recal_disabled and is_running:
        st.info("ℹ️ Stop monitoring before calibrating")
    
    if st.button("🔄 Recalibrate", disabled=recal_disabled, key="recalibrate_btn"):
        if is_running:
            service_mgr.stop_background()
            time.sleep(1)
        
        success = cal_runner.start_calibration(
            duration_sec=cal_duration,
            camera_index=cal_camera,
            target_fps=8.0
        )
        if success:
            st.success("Calibration started!")
            st.rerun()
        else:
            st.error("Failed to start calibration")

st.divider()

# Sensitivity Section
st.header("🎯 Sensitivity")
config = st.session_state.config_manager.load_config()
preset = st.selectbox("Preset", ["sensitive", "standard", "conservative"], 
                      index=["sensitive", "standard", "conservative"].index(config['state_config']['preset']))
col1, col2, col3 = st.columns(3)
neck = col1.slider("Neck (°)", 5.0, 20.0, config['state_config']['slouch_threshold_deg'], 0.5)
torso = col2.slider("Torso (°)", 5.0, 20.0, config['state_config']['forward_lean_threshold_deg'], 0.5)
lateral = col3.slider("Lateral (cm)", 1.0, 8.0, config['state_config']['lateral_lean_threshold_cm'], 0.5)

if st.button("💾 Save Sensitivity"):
    config['state_config']['preset'] = preset
    config['state_config']['slouch_threshold_deg'] = neck
    config['state_config']['forward_lean_threshold_deg'] = torso
    config['state_config']['lateral_lean_threshold_cm'] = lateral
    st.session_state.config_manager.save_config(
        StateConfig.from_preset(SensitivityPreset(preset)),
        NudgeConfig(**config['nudge_config']),
        config['system_config']
    )
    st.success("✅ Saved! Restart monitoring to apply.")

st.divider()

# System Settings Section
st.header("⚙️ System Settings")

# Login Item toggle
login_status = get_login_item_status()
if login_status['available']:
    st.subheader("Launch at Login")
    
    current_status = "✅ Enabled" if login_status['enabled'] else "❌ Disabled"
    st.write(f"**Status:** {current_status}")
    
    if st.checkbox("Launch DeskCoach at login", value=login_status['enabled'], key="login_item_toggle"):
        if not login_status['enabled']:
            # Need to enable
            success, message = toggle_login_item()
            if success:
                st.success(f"✅ {message}")
                st.rerun()
            else:
                st.error(f"❌ {message}")
    else:
        if login_status['enabled']:
            # Need to disable
            success, message = toggle_login_item()
            if success:
                st.success(f"✅ {message}")
                st.rerun()
            else:
                st.error(f"❌ {message}")
    
    st.caption(f"App path: {login_status['app_path']}")
else:
    st.info("ℹ️ Login Item control only available when running as .app bundle")

st.divider()

# Privacy Section
st.header("🔒 Privacy")
st.markdown('<div class="privacy-notice">🛡️ No frames saved - Only metrics</div>', unsafe_allow_html=True)
if st.button("🗑️ Purge All Data"):
    if st.button("✅ Confirm Purge"):
        st.session_state.event_logger.purge_logs()
        st.session_state.config_manager.purge_config()
        st.success("✅ Purged!")

st.divider()

# Stats Section
st.header("📈 Today's Stats")
events = st.session_state.event_logger.get_recent_events(100)
nudges = [e for e in events if e['event_type'] == 'nudged']
st.metric("Total Nudges", len(nudges))

st.divider()

# Service Logs
st.header("📝 Service Logs")
if is_running:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        log_lines = st.slider("Lines to show", 10, 100, 30, key="log_lines")
    with col2:
        if st.button("🔄 Refresh Logs", key="refresh_logs"):
            st.rerun()
    with col3:
        if st.button("🗑️ Clear Logs", key="clear_logs"):
            if hasattr(service_mgr, 'clear_logs'):
                service_mgr.clear_logs()
                st.success("Logs cleared")
            else:
                st.warning("Restart UI to enable this feature")
            st.rerun()
    
    # Get logs (with fallback for older ServiceManager)
    if hasattr(service_mgr, 'tail_logs'):
        logs = service_mgr.tail_logs(lines=log_lines)
    else:
        logs = "⚠️ Restart the UI to enable log viewing.\n\nThe ServiceManager was updated but the UI is using a cached instance."
    st.code(logs, language="text", line_numbers=False)
else:
    st.info("Start monitoring to see logs")

st.divider()

# Event Log
st.header("📋 Event Log")
if events:
    df = pd.DataFrame(events)
    st.dataframe(df[['timestamp', 'event_type', 'state', 'reason']].tail(20), width='stretch')
else:
    st.info("No events yet")

st.caption("DeskCoach v1 - Privacy-first posture monitoring")
