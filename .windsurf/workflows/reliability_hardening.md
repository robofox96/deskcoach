---
description: Make the app robust in real-world conditions.
auto_execution_mode: 1
---

Command name: /reliability_hardening
Goal: Make the app robust in real-world conditions.

Inputs: rules; existing modules.

Steps:

Multi-person scenes: pick largest/closest; else paused.

Low light / occlusion → paused.

FPS governor: keep within CPU budget; degrade gracefully.

Camera errors: self-recover, handle unplug/replug.

Confirm no frame writes to disk; privacy review.

Short run test (30–60 min) to validate nudge rate & CPU usage.

Deliverables: reliability improvements + checklist results.
Out of scope: feature additions.