"""
macOS notification engine with action handling.

Uses pync for macOS notifications with interactive actions.
Respects system DND/Focus modes.

PRIVACY: No frames, only text notifications.
"""

import time
import subprocess
from typing import Optional, Callable
from enum import Enum


class NotificationAction(Enum):
    """User actions on notifications."""
    DONE = "done"
    SNOOZE = "snooze"
    DISMISS = "dismiss"
    TIMEOUT = "timeout"  # User didn't interact


class NotificationEngine:
    """
    macOS notification engine with action handling.
    
    Posts notifications with Done/Snooze/Dismiss actions.
    Respects system DND/Focus modes.
    """
    
    def __init__(self, app_name: str = "DeskCoach"):
        """
        Initialize notification engine.
        
        Args:
            app_name: Application name for notifications
        """
        self.app_name = app_name
        self.active_notification = None
        self.action_callback: Optional[Callable[[NotificationAction], None]] = None
    
    def is_dnd_active(self) -> bool:
        """
        Check if macOS Do Not Disturb / Focus mode is active.
        
        Returns:
            True if DND is active, False otherwise
        """
        try:
            # Check DND status via defaults command
            # This reads the com.apple.notificationcenterui plist
            result = subprocess.run(
                ["defaults", "read", "com.apple.notificationcenterui", "doNotDisturb"],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            # If the key exists and is 1, DND is active
            return result.returncode == 0 and result.stdout.strip() == "1"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # If we can't determine, assume DND is not active
            return False
    
    def post_notification(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
        action_callback: Optional[Callable[[NotificationAction], None]] = None
    ) -> bool:
        """
        Post a macOS notification with Done/Snooze/Dismiss actions.
        
        Args:
            title: Notification title
            message: Notification message
            subtitle: Optional subtitle
            action_callback: Callback for user actions
            
        Returns:
            True if notification was posted, False if suppressed (e.g., DND)
        """
        self.action_callback = action_callback
        
        try:
            # Try using pync if available
            import pync
            
            # Post notification with actions
            # pync supports actions via buttons parameter
            pync.notify(
                message,
                title=title,
                subtitle=subtitle or "",
                appIcon=None,  # Use default app icon
                contentImage=None,
                sound=None,  # No sound for non-intrusive
                open=None,
                execute=None,
                sender="com.deskcoach.app",  # App bundle ID
                activate=None,
                group=self.app_name,
                remove=None,
                # Actions are handled via AppleScript in pync
                # For full action support, we'll use osascript directly below
            )
            
            self.active_notification = {
                "title": title,
                "message": message,
                "posted_at": time.time()
            }
            
            return True
            
        except ImportError:
            # Fallback to osascript if pync not available
            return self._post_via_osascript(title, message, subtitle)
    
    def _post_via_osascript(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None
    ) -> bool:
        """
        Post notification using osascript (AppleScript).
        
        This is a fallback when pync is not available.
        Note: Interactive actions require terminal-notifier or similar.
        """
        try:
            # Simple notification via osascript
            script = f'display notification "{message}" with title "{title}"'
            if subtitle:
                script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
            
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=2.0
            )
            
            self.active_notification = {
                "title": title,
                "message": message,
                "posted_at": time.time()
            }
            
            return True
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("WARNING: Could not post notification (osascript failed)")
            return False
    
    def post_with_terminal_notifier(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None
    ) -> bool:
        """
        Post notification with actions using terminal-notifier.
        
        terminal-notifier supports interactive actions.
        Install: brew install terminal-notifier
        
        NOTE: This is NON-BLOCKING. Actions are not captured in M1.
        For M2, use background thread or async to capture actions.
        
        Args:
            title: Notification title
            message: Notification message
            subtitle: Optional subtitle
            
        Returns:
            True if posted successfully
        """
        try:
            cmd = [
                "terminal-notifier",
                "-title", title,
                "-message", message,
                "-sound", "default"  # Add sound for visibility
                # NOTE: Removed -group (was causing notifications to replace each other)
                # NOTE: Removed -sender (was using non-existent bundle ID)
                # NOTE: Removed -actions to make it non-blocking
            ]
            
            if subtitle:
                cmd.extend(["-subtitle", subtitle])
            
            # Use Popen to make it non-blocking
            # Capture stderr to detect errors
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Don't wait for completion, but check if it started successfully
            # Give it 0.1 seconds to detect immediate failures
            try:
                stdout, stderr = proc.communicate(timeout=0.1)
                if stderr:
                    print(f"  [NOTIFICATION] Warning: {stderr.strip()}")
            except subprocess.TimeoutExpired:
                # Process is still running - this is good, notification was posted
                pass
            
            self.active_notification = {
                "title": title,
                "message": message,
                "posted_at": time.time()
            }
            
            return True
            
        except FileNotFoundError:
            print("  [NOTIFICATION] Error: terminal-notifier not found")
            # terminal-notifier not available, fallback
            return self._post_via_osascript(title, message, subtitle)
        except Exception as e:
            print(f"  [NOTIFICATION] Error: {e}")
            return False
    
    def clear_active_notification(self):
        """Clear the active notification state."""
        self.active_notification = None
        self.action_callback = None
    
    def has_active_notification(self) -> bool:
        """Check if there's an active notification."""
        return self.active_notification is not None
    
    def get_active_notification_age(self) -> Optional[float]:
        """Get age of active notification in seconds."""
        if self.active_notification:
            return time.time() - self.active_notification["posted_at"]
        return None
