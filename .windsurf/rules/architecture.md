---
trigger: always_on
description: Rules to apply for any architectural decisions.
---

High-Level

Background Service (Python): camera → pose landmarks → metrics → state machine → notifications → logs.

Local UI (Streamlit): start/stop, camera selector, thresholds, cooldowns, quick stats.

Storage: SQLite (or JSON) for baselines, settings, metrics/events.

Packaging: PyInstaller (macOS app first; Windows later).

Pose & Metrics

Model: MediaPipe Pose/BlazePose (33 landmarks) or similar.

FPS: 5–10 target; adaptive if CPU spikes.

Compute per frame:

Neck flexion: angle (ear–shoulder vs vertical).

Torso flexion: angle (hip–shoulder vs vertical).

Lateral lean: shoulder height Δ or ear x-offset asymmetry.

Smooth via EMA; evaluate on sliding windows (30–60s).

Confidence gating: if landmarks < threshold → paused.

Personalization

Calibration: 20–30s “upright” capture → median baselines + shoulder width proxy.

Adaptive thresholds (baseline + deltas).

Slow baseline drift correction (EMA) only when in good.

State Machine

States: good, slouch, forward_lean, lateral_lean, paused.

Enter “issue” state only if condition is sustained over window.

Leave when metrics return below threshold for a recovery window.

Notifications

Actions: Done, Snooze 15m, Dismiss.

Cooldowns: Done (30m), Snooze (15m), Dismiss (increase threshold temporarily).

Reliability

Multi-person: track the largest/closest person; else paused.

Low light / occlusion: paused.

Self-recover camera errors; FPS governor; metrics-only logs.