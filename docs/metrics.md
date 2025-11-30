DeskCoach — Metrics & Signal Processing (v1)
Landmarks (single person)

Use head/shoulders/hips landmarks. Confidence gating: if landmark confidence below a threshold, evaluation pauses (state = paused).

Core Metrics (per frame, relative rather than absolute)

Neck flexion: the angle between the shoulder→ear vector and the vertical axis in the image plane.

Torso flexion: the angle between the hip→shoulder vector and the vertical axis.

Lateral lean: asymmetry captured by shoulder height difference and/or horizontal ear offset relative to midline.

Note: Using relative vectors makes results more robust to camera tilt.

Smoothing

Apply an exponential moving average to each metric to suppress jitter.

Maintain sliding windows (e.g., last 30–60 seconds) for sustained-condition checks.

Calibration

User sits comfortably upright for 20–30 seconds.

Baselines: median neck and torso angles over the window, plus a shoulder-width proxy for scale.

Store in local config; allow re-calibration at any time.

Personalized Thresholds (initial defaults)

Slouch if neck flexion exceeds baseline by a delta (typical starting point: 15 degrees) sustained for 45 seconds.

Forward lean if torso flexion exceeds baseline by a delta (typical starting point: 12 degrees) sustained for 45 seconds.

Lateral lean if shoulder height difference exceeds baseline by a scale-adjusted delta (typical starting point: 3–4 cm equivalent) sustained for 60 seconds.

These are starting points; make them user-tunable in settings.

State Machine

States: good, slouch, forward_lean, lateral_lean, paused.
Rules:

Enter an “issue” state only when the sustained condition window is satisfied.

Exit when metrics recover below threshold for a recovery window.

Apply slow baseline drift (small EMA) only when in good.

Nudge Policy

Trigger at most one nudge per sustained issue window.

Actions: Done (adds a cooldown), Snooze 15m, Dismiss (temporary threshold backoff).

Always log state transitions and user actions.

Data Model (high level)

Config: baselines, thresholds, windows, cooldowns, device settings.

Metrics snapshot: timestamp, smoothed metrics, confidence, state.

Event log: state entered, notification shown, action taken, cooldowns applied.

Performance Targets

FPS: 5–10 (6–8 typical).

CPU: < 15% in normal use on a recent macOS laptop.

Pause evaluation when confidence is low to save resources and avoid false positives.