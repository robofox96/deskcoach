---
description: Capture neutral posture baseline & persist.
auto_execution_mode: 1
---

Command name: /calibration_flow
Goal: Capture neutral posture baseline & persist.

Inputs: rules/architecture.md, rules/privacy.md.

Steps:

Start a 20–30s capture while user sits upright.

Aggregate neck/torso metrics (median over window).

Compute shoulder width proxy for scale.

Persist baselines & scale locally (JSON/SQLite).

Provide re-calibrate function & simple progress UI.

Deliverables: calibration module + stored baselines + re-calibrate entry point.
Out of scope: heuristic thresholds, notifications.