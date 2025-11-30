---
description: Determine posture state using sustained windows.
auto_execution_mode: 1
---

Command name: /state_machine
Goal: Determine posture state using sustained windows.

Inputs: all rules; metrics from pose loop; baselines from calibration.

Steps:

Define states: good, slouch, forward_lean, lateral_lean, paused.

Thresholds (initial):

Slouch if neck flexion > baseline + 15° for ≥45s.

Forward lean if torso flexion > baseline + 12° for ≥45s.

Lateral lean if shoulder Δheight > baseline + 3–4 cm for ≥60s.

Debounce: require continuous condition (no oscillation).

Recovery: exit state after metrics drop below threshold for a recovery window.

Auto-drift: small EMA on baselines while in good.

Emit state changes as events.

Deliverables: state machine module emitting state transitions + reasons.
Out of scope: notifications, UI wiring.