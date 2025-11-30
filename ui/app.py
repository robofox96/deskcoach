"""
DeskCoach Streamlit UI - Live status with IPC bridge
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

from core import CalibrationStorage, StateConfig, NudgeConfig, SensitivityPreset, EventLogger
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

# Auto-refresh every 1 second
st_autorefresh(interval=1000, key="datarefresh")

# Initialize session state
if 'config_manager' not in st.session_state:
    st.session_state.config_manager = ConfigManager()
if 'calibration_storage' not in st.session_state:
    st.session_state.calibration_storage = CalibrationStorage()
if 'event_logger' not in st.session_state:
    st.session_state.event_logger = EventLogger()

st.title("🪑 DeskCoach")
st.caption("Privacy-first posture monitoring - No frames saved")

# Load live status
def load_live_status():
    """Load live status from status.json"""
    status_file = Path("storage/status.json")
    
    if not status_file.exists():
        return None, "File not found"
    
    try:
        # Check if file is stale (>3 seconds old)
        mtime = status_file.stat().st_mtime
        age = time.time() - mtime
        
        if age > 3.0:
            return None, f"Stale ({age:.1f}s old)"
        
        with open(status_file, 'r') as f:
            data = json.load(f)
        
        return data, None
    except Exception as e:
        return None, str(e)

status, error = load_live_status()

# Status Section
st.header("📊 Live Status")

if error:
    st.markdown(f"""
    <div class="waiting-banner">
        <strong>⏳ Waiting for background service...</strong><br>
        Reason: {error}<br>
        <br>
        To start monitoring, run in a terminal:<br>
        <code>python dev_runner.py --diagnostics</code>
    </div>
    """, unsafe_allow_html=True)
else:
    # Display live status
    state = status['state']
    if state == 'good':
        st.markdown(f'<p class="status-good">● GOOD - Posture within thresholds</p>', unsafe_allow_html=True)
    elif state == 'paused':
        st.markdown(f'<p class="status-paused">⏸ PAUSED - Low confidence or no pose detected</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="status-issue">⚠ {state.upper().replace("_", " ")} - Posture issue detected</p>', unsafe_allow_html=True)
    
    # Metrics in columns
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
        st.metric("Neck Flexion", f"{neck:.1f}°", 
                 delta=f"{delta:+.1f}° vs threshold",
                 delta_color="inverse")
    
    with col2:
        torso = metrics['torso_deg']
        torso_thresh = thresholds['torso_abs_deg']
        delta = torso - torso_thresh
        st.metric("Torso Flexion", f"{torso:.1f}°",
                 delta=f"{delta:+.1f}° vs threshold",
                 delta_color="inverse")
    
    with col3:
        lateral = metrics['lateral']
        lateral_thresh = thresholds['lateral_abs']
        delta = lateral - lateral_thresh
        st.metric("Lateral Lean", f"{lateral:.3f}",
                 delta=f"{delta:+.3f} vs threshold",
                 delta_color="inverse")
    
    # Detection path
    if status['detection_path'] != 'none':
        st.info(f"🎯 Detection path: **{status['detection_path'].upper()}**")
    
    # Window stats (diagnostics)
    with st.expander("📊 Window Statistics"):
        ws = status['window_stats']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Slouch Window**")
            st.write(f"Above: {ws['slouch_above_fraction']*100:.0f}%")
            st.write(f"Cumulative: {ws['slouch_cumulative_sec']:.1f}s")
            st.write(f"Max gap: {ws['slouch_max_gap_sec']:.1f}s")
        
        with col2:
            st.write("**Forward Lean Window**")
            st.write(f"Above: {ws['forward_above_fraction']*100:.0f}%")
            st.write(f"Cumulative: {ws['forward_cumulative_sec']:.1f}s")
            st.write(f"Max gap: {ws['forward_max_gap_sec']:.1f}s")
        
        with col3:
            st.write("**Lateral Lean Window**")
            st.write(f"Above: {ws['lateral_above_fraction']*100:.0f}%")
            st.write(f"Cumulative: {ws['lateral_cumulative_sec']:.1f}s")
            st.write(f"Max gap: {ws['lateral_max_gap_sec']:.1f}s")
    
    # Policy status
    st.subheader("Policy Status")
    policy = status['policy']
    
    status_parts = []
    if policy['cooldown_sec_left'] and policy['cooldown_sec_left'] > 0:
        status_parts.append(f"⏱ Cooldown: {policy['cooldown_sec_left']/60:.1f}m")
    if policy['snooze_sec_left'] and policy['snooze_sec_left'] > 0:
        status_parts.append(f"😴 Snooze: {policy['snooze_sec_left']/60:.1f}m")
    if policy['backoff_sec_left'] and policy['backoff_sec_left'] > 0:
        status_parts.append(f"🔼 Backoff: {policy['backoff_sec_left']/60:.1f}m")
    if policy['last_nudge_age_sec'] is not None:
        status_parts.append(f"📢 Last nudge: {policy['last_nudge_age_sec']/60:.1f}m ago")
    if policy['dnd_queued_count'] > 0:
        status_parts.append(f"🌙 DND: {policy['dnd_queued_count']} queued")
    
    if status_parts:
        st.info(" | ".join(status_parts))
    else:
        st.success("No active cooldowns or restrictions")

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
    st.success("✅ Saved! Restart dev_runner to apply.")

st.divider()

# Calibration Section
st.header("📏 Calibration")
cal_status = st.session_state.calibration_storage.get_calibration_status()
if cal_status['calibrated']:
    st.success(f"✅ Calibrated: {cal_status['calibrated_at']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Neck", f"{cal_status['neck_baseline']:.1f}°")
    col2.metric("Torso", f"{cal_status['torso_baseline']:.1f}°")
    col3.metric("Lateral", f"{cal_status['lateral_baseline']:.3f}")
    st.info("To recalibrate, run: `python dev_runner_calibrate.py`")
else:
    st.warning("⚠️ Not calibrated. Run: python dev_runner_calibrate.py")

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

# Event Log
st.header("📋 Event Log")
if events:
    df = pd.DataFrame(events)
    st.dataframe(df[['timestamp', 'event_type', 'state', 'reason']].tail(20), use_container_width=True)
else:
    st.info("No events yet")

st.caption("DeskCoach v1 - Privacy-first posture monitoring")
