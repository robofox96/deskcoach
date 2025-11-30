DeskCoach — macOS Platform Notes
Permissions (TCC)

Camera access is gated by macOS privacy (Transparency, Consent, and Control). First use triggers a system prompt; permission can be revoked or granted in System Settings → Privacy & Security → Camera.

Notifications require user approval the first time the app posts a notification. Users can manage in System Settings → Notifications.

If permissions get into a bad state (e.g., denied then changed), a full app restart is often required for changes to take effect.

Resetting Permissions (for QA)

You can reset camera or notifications permissions via system tools. If reset is needed, document the steps in team notes and rerun the permission prompts. (Avoid including destructive commands in user-facing flows.)

Packaging (v1)

Package with a single-binary approach. For first internal builds, unsigned is acceptable; expect the “unverified developer” dialog.

Later milestones: enable hardened runtime, code signing, and notarization so the app launches without warnings.

Autostart

Provide a toggle to add/remove the app from Login Items (System Settings → General → Login Items).

Respect system Do Not Disturb / Focus modes (do not circumvent them).

Performance & Thermals

Keep FPS at 5–10. If the laptop heats up or CPU usage exceeds budget, drop FPS automatically.

Pause evaluation when confidence is low to save compute and avoid false positives.

Sleep/Wake & Camera Conflicts

On wake, re-initialize the camera session and resume the loop gracefully.

If the camera is busy (e.g., video call app), back off and retry periodically; show “paused” clearly in the UI.

Privacy UX

Provide a clear indicator when monitoring is active.

Expose “Pause monitoring” and “Purge data” in one click.

Do not write frames to disk under any circumstance in v1.

Windows Later

Match feature parity; swap notification and camera access layers accordingly.

Expect slightly different CPU/FPS dynamics and test thresholds separately.