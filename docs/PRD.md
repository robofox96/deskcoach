DeskCoach — Product Requirements (v1)
Mission

A macOS-first, local-only posture coach. Uses the laptop webcam to estimate pose and gives gentle nudges when posture issues are sustained. Never saves images; only metrics.

Goals (v1)

Posture detection for a single user at a desk (neck flexion, torso flexion, lateral lean).

One-time calibration that personalizes thresholds.

Non-annoying nudges with actions (Done, Snooze, Dismiss) and cooldowns.

Minimal local UI: start/stop, camera selector, thresholds, today’s stats.

Local logging for events and metrics; simple weekly summary.

Packaged macOS app; Windows later.

Non-Goals (v1)

Hydration/gamification/social features.

Multi-user management or cloud sync.

Storing image/video frames or using external services.

Success Criteria

False nudge rate < 15% over a typical workday.

Typical CPU usage < 15% at 6–8 FPS.

Calibration persists for ≥ 1 week of normal use.

One-click purge deletes all stored data; zero frames ever saved.

Users & Use Cases

Individual knowledge workers on laptops who sit long hours.

Primary loop: work → sustained slouch detected → one nudge → micro-routine → back to work.

Occasional UI visit for settings, recalibration, or reviewing stats.

Experience Principles

Local & private; defaults to minimal collection.

Frictionless and respectful; fewer, higher-quality nudges.

Transparent: show current state and why a nudge was triggered.

Feature List (v1)

Pose loop at 5–10 FPS with confidence gating and smoothing.

Calibration flow (20–30 seconds) to set personal baselines.

Heuristics & state machine with sustained-condition windows.

Notifications with actions and cooldown/backoff policy.

Settings & today’s stats page; one-click purge; pause monitoring.

Local logs and export (CSV) in a later milestone.

Constraints & Risks

Lighting variability; occlusion; multi-person presence.

macOS camera permissions and notification permissions.

Laptop thermal limits; must degrade gracefully.

Privacy trust: no frames saved; make this highly visible.

Acceptance (Definition of Done, v1)

End-to-end posture nudge loop works for a full work session without spam.

UI shows state, metrics preview, and today’s basic stats.

Settings persist; purge deletes all stored data.

Packaging produces a runnable macOS app; minimal permission friction.

Manual tests pass (see docs/testing.md).