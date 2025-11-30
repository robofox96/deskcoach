---
description: Non-annoying notifications with action handling.
auto_execution_mode: 1
---

Command name: /notif_policy
Goal: Non-annoying notifications with action handling.

Inputs: rules (project, architecture, privacy, M1 checklist), state events.

Steps:

On entering an “issue” state, check last nudge time & cooldowns.

Show notification with Done/Snooze 15m/Dismiss.

On Done: record compliance; cooldown 30m.

On Snooze: suppress 15m.

On Dismiss: apply temporary threshold backoff (e.g., +5° for 60m).

Log all events + user actions.

Deliverables: notification policy module + event logger.
Out of scope: UI settings page (handled elsewhere).