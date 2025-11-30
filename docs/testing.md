DeskCoach — Test Plan (v1)
Objectives

Verify the end-to-end loop: pose → metrics → sustained detection → notification → action handling → logging, under realistic desk conditions.

Environments

macOS (Apple Silicon preferred).

Built app (packaged) and dev run (unpackaged).

Test in daylight and low-light conditions.

Test Scenarios (manual)

Neutral sit for 2 minutes
Expected: state = good; no nudges; low CPU; steady metrics.

Sustained slouch for 60 seconds
Expected: one nudge after sustain window; actions available; cooldown applied after Done.

Forward lean for 60 seconds
Expected: one nudge; correct state label; cooldown applied.

Lateral lean for 70 seconds
Expected: one nudge; lateral state recognized; not confused with slouch.

Out of frame / occlusion
Expected: state = paused; no nudges.

Low light / backlight
Expected: state shifts to paused if confidence drops; no nudges.

Multi-person in background
Expected: track largest/closest; if ambiguous → paused; no false nudges.

Dismiss behavior
Expected: dismiss twice leads to temporary threshold backoff (fewer nudges next hour).

Snooze behavior
Expected: no further nudges for snooze duration; resumes afterward.

Recalibration
Expected: new baselines stored; thresholds re-applied; behavior stable.

Metrics to Record During Tests

Nudge count per hour and acceptance rate (Done vs Snooze vs Dismiss).

False positives (nudges during clearly good posture).

CPU usage range at target FPS.

Confidence drop frequency and pause durations.

Regression Checklist (before each release)

Calibration persists across restarts.

Settings persist and take effect immediately.

One-click purge removes metrics, events, and settings.

No frames written to disk.

Notifications work after app restart and across sleep/wake cycles.

Camera busy conflicts handled gracefully (app recovers).

Exit Criteria for v1

All 10 scenarios pass in a single session.

False nudge rate < 15% on a 3–4 hour test session.

CPU within budget at target FPS.

No image files on disk after multiple sessions.