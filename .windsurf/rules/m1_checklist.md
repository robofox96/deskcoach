---
trigger: always_on
description: Milestone M1 — Definition of Done
---

Webcam loop (5–10 FPS) with pose landmarks and EMA-smoothed neck/torso/lateral metrics.

Calibration flow: baselines (median) + shoulder width proxy persisted.

Heuristics & state machine with sustained-condition windows and confidence gating.

OS notifications with Done/Snooze/Dismiss + cooldown/backoff logic.

Local logs (SQLite/JSON) recording events & aggregate metrics.

Minimal UI: start/stop, camera selector, thresholds, cooldown, live state, today’s stats.

Packaging: runnable macOS app (unsigned OK for M1), readme for permissions.

No frames saved; metrics only; one-click purge.

CPU usage under target on a short test (30–60 min).