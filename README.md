## DeskCoach (macOS-first, local-only)

DeskCoach is a tiny posture coach that runs **entirely on your Mac**, uses your laptop webcam to estimate pose (**no images saved**), and sends polite nudges when sustained posture issues are detected.

v1 focuses on **posture only** (hydration and other habits come later).

---

## Why

Long workdays → slouching, neck/shoulder pain, and no breaks. DeskCoach helps by:

- **Detecting sustained posture issues** (neck flexion, torso lean, lateral lean).
- **Nudging gently**, with clear actions and cooldowns.
- **Respecting privacy** by never saving frames and keeping all data local.

---

## Key Principles

- **Local-first & private**  
  - No frames or video are ever written to disk.  
  - Only posture metrics (angles, timestamps, states, nudge events) are stored.  
  - No network calls, telemetry, or cloud sync in v1.

- **Low friction**  
  - Runs as a lightweight background service.  
  - Minimal Streamlit UI for start/stop, calibration, and settings.

- **Non-annoying**  
  - Sustained-condition detection (slouch must persist over a window).  
  - Cooldowns and snooze to avoid nudge spam.  
  - Clear actions: **Done / Snooze / Dismiss**.

---

## What v1 Does

- **Pose & Metrics**  
  - Webcam → MediaPipe Pose (BlazePose) → 33 landmarks.  
  - Computes neck flexion, torso flexion, and lateral lean at ~5–10 FPS.  
  - EMA smoothing + sliding windows for robust state detection.

- **Calibration**  
  - 20–30s "neutral posture" capture.  
  - Computes median baselines and a shoulder-width proxy.  
  - Baseline persisted locally and used to personalize thresholds.

- **Personalized Detection**  
  - Thresholds are defined **relative to your baseline**, not absolute angles.  
  - State machine for `good`, `slouch`, `forward_lean`, `lateral_lean`, `paused`.

- **Notifications & Policy**  
  - OS notifications with actions: **Done / Snooze 15m / Dismiss**.  
  - Cooldowns, backoff after repeated dismissals, and DND-aware behavior.  
  - Local event logging of nudges and responses.

- **UI (Streamlit)**  
  - Live posture status and metrics (via `storage/status.json`).  
  - Start/Stop/Restart background monitoring service.  
  - Integrated calibration flow with progress bar and baselines.  
  - Sensitivity configuration (presets + thresholds).  
  - Privacy controls (Purge Data).  
  - Today’s stats and recent event log.

- **Storage**  
  - `storage/calibration.json` – calibration baseline.  
  - `storage/ui_config.json` – UI + state/nudge/system configuration.  
  - `storage/events.jsonl` – nudge and state-change events (metrics only).  
  - `storage/status.json` – live status snapshot for UI.  
  - Transient IPC/process files (`*.pid`, `service.json`, `calibration_status.json`, `calibration.lock`) are **git-ignored**.

---

## What v1 Explicitly Does *Not* Do

- Hydration or break reminders (planned for a later version).  
- Storing images, screenshots, or video frames.  
- Cloud sync, external APIs, or any outbound network traffic.

---

## High-Level Architecture

- **Background Service (`dev_runner.py`)**  
  - Runs the `PoseLoop`: camera → pose landmarks → smoothed metrics.  
  - Feeds a posture state machine + notification policy.  
  - Publishes a compact `status.json` snapshot for the UI.

- **Calibration (`dev_runner_calibrate.py` + `CalibrationRunner`)**  
  - Separate subprocess with a rich progress callback writing `calibration_status.json`.  
  - UI can start/cancel calibration and show progress.

- **Local UI (Streamlit)**  
  - `ui/app_with_controls.py` – primary UI for v1 (system controls + status + calibration).  
  - `ui/app.py` – lean live-status dashboard useful during development.

- **Core Library (`core/`)**  
  - Pose loop, metrics, state machine, notification policy, calibration, storage, IPC helpers, and process runners.

- **Packaging**  
  - Target: PyInstaller-based macOS app bundle.  
  - Windows support is a later milestone.

---

## Installation

### Prerequisites

- macOS with a built-in or external webcam.  
- Python **3.11 or 3.12** (MediaPipe does **not** support 3.13 yet).  
- `git` and a working terminal (e.g., Terminal, iTerm, IDE terminal).

### 1. Clone the Repository

```bash
git clone https://github.com/robofox96/deskcoach.git
cd deskcoach
```

### 2. Create & Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

For a pinned Python 3.12 setup (as used in development), see `QUICKSTART.md`.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running DeskCoach

There are two main ways to run the app:

1. **Full app (recommended):** Background service + Streamlit UI with controls.  
2. **Dev mode:** CLI pose loop and calibration scripts.

### Option A – Full App with UI Controls (Recommended)

1. **Start the Streamlit UI with controls:**

   ```bash
   # From project root
   streamlit run ui/app_with_controls.py
   ```

2. **In the browser UI:**

   - Go to the **📏 Calibration** section.  
   - If not calibrated, click **Recalibrate** and follow the on-screen timer (sit upright for ~25s).  
   - Once calibration completes, you’ll see baseline metrics.

3. **Start monitoring:**

   - In **🎮 System Controls**, click **Start Monitoring**.  
   - Live status will update once `status.json` is produced by the background service.  
   - Use **Stop Monitoring** or **Restart** as needed.

4. **Privacy & data controls:**

   - Use **🗑️ Purge All Data** in the UI to delete config + events.  
   - No frames are ever stored; purging removes metrics and settings.

> The UI layout, sections, and additional details are documented in `ui/README_UI.md`.

### Option B – Dev Mode (CLI)

For low-level debugging or headless environments:

1. **One-time calibration (CLI):**

   ```bash
   source venv/bin/activate
   python dev_runner_calibrate.py
   ```

   - Follow on-screen instructions to sit upright for ~25s.  
   - Baseline is saved to `storage/calibration.json`.

2. **Run the pose loop directly:**

   ```bash
   source venv/bin/activate

   # Default: 8 FPS, camera 0, print every 2s
   python dev_runner.py

   # Custom settings
   python dev_runner.py --fps 6.0 --camera 0 --interval 3.0
   ```

   - Logs metrics to the terminal and writes live status to `storage/status.json`.

> For a step-by-step dev walkthrough, see `QUICKSTART.md`.

---

## Repository Layout

```text
core/            # Pose loop, metrics, state machine, notifications, calibration, IPC, runners
ui/              # Streamlit apps and UI config manager
docs/            # Design docs (e.g. UI_CONTROLS_IMPLEMENTATION.md)
storage/         # Runtime storage (JSON/JSONL); created at runtime, mostly git-ignored
dev_runner.py    # Background monitoring service entry point (CLI)
dev_runner_calibrate.py  # Calibration runner (CLI & UI backend)
QUICKSTART.md    # Detailed dev quickstart
requirements.txt # Python dependencies
```

---

## Privacy & Data

- **Never stored:**  
  - Camera frames, images, screenshots, or video.  
  - Personal identifying information.

- **Stored locally only:**  
  - Calibration baselines (angles, sample counts, timestamps).  
  - Live posture metrics and state snapshots.  
  - Nudge and action events.  
  - UI and system configuration.

- **Purge:**  
  - The **Purge All Data** button in the UI deletes logs and config (`events.jsonl`, `ui_config.json`, etc.).  
  - Calibration data can also be cleared as part of development workflows.

- **Network access:**  
  - DeskCoach v1 makes **no outbound network calls**.

---

## Troubleshooting

- **Camera not accessible**  
  - Grant camera permission in **System Settings → Privacy & Security → Camera**.  
  - Ensure Terminal/IDE has camera access.  
  - Try a different camera index: `--camera 1`.

- **High CPU usage**  
  - Reduce FPS (e.g., `--fps 6.0`).  
  - Close other camera-using apps.  
  - Target is `< 15%` CPU on a typical laptop at 6–8 FPS.

- **Always PAUSED / low confidence**  
  - Improve lighting and avoid strong backlight.  
  - Sit closer and ensure your upper body is fully in frame.  
  - Verify camera works (e.g., with Photo Booth).

- **Too many or too few nudges**  
  - Adjust thresholds and presets in the **🎯 Sensitivity** section of the UI.  
  - Increase sustain windows or cooldowns to reduce nudge frequency.

More detailed debugging tips live in:

- `QUICKSTART.md`  
- `ui/README_UI.md`  
- `docs/UI_CONTROLS_IMPLEMENTATION.md`

---

## Roadmap (Short)

- **M1 (current)** – Pose loop, calibration, heuristics, notifications, local UI, basic logs.  
- **M2** – Weekly stats, CSV export, richer UI polish, packaging as a macOS app bundle.  
- **Future** – Hydration nudger, richer micro-routine library, multi-platform support.

---

## License

TBD.
