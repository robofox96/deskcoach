---
trigger: always_on
---

Project: DeskCoach (macOS-first, Windows later)
Mission: A local-only posture coach that uses the laptop webcam to estimate pose and sends polite nudges for sustained posture issues. No images are saved; only metrics.

Scope (v1)

Posture only (neck/torso/lateral lean), 5–10 FPS camera loop.

One-time calibration (neutral posture baseline).

Personalized thresholds (relative to baseline).

Non-annoying notifications (Done/Snooze/Dismiss) with cooldowns.

Minimal local UI for settings & today’s stats.

Local logging (SQLite/JSON) of metrics & events.

Packaging for macOS; Windows support later.

Non-goals (v1)

Hydration nudger (v2 feature).

Cloud services, external APIs, or storing frames.

Multi-user / multi-seat deployment.

Success Criteria (v1)

< 15% false nudges in a typical workday.

CPU budget: target < 15% on a typical laptop at 6–8 FPS.

Calibration persists; no re-calibration needed within a week.

Privacy: never save frames; one-click purge.

Key Principles

Local-first & private

Sustained-condition detection (debounce & grace windows)

Gentle UX (cooldowns, DND-friendly)

Maintainable (clear modules, logs, tests later)