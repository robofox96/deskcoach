---
description: Implement the background pose loop producing stable metrics.
auto_execution_mode: 1
---

Command name: /m1_pose_loop
Goal: Implement the background pose loop producing stable metrics.

Inputs the agent should read:

rules/project.md, rules/architecture.md, rules/privacy.md, this workflow.

Steps (no code, just tasks):

Initialize webcam at target FPS (5–10).

Run on-device pose; handle confidence scores.

Compute neck/torso/lateral metrics per frame.

Apply EMA smoothing; expose rolling 30–60s buffers.

Implement confidence gating → paused if low.

Telemetry: print minimal metrics at 2s intervals (dev only).

Respect privacy: never write frames to disk.

Deliverables: background module with a clear API to retrieve smoothed metrics + confidence + state.
Out of scope: calibration, notifications, UI.