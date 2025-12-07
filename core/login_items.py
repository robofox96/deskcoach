"""
Login Items management for macOS.

Allows adding/removing DeskCoach from Login Items (launch at login).
Uses osascript to interact with System Events.

PRIVACY: No frames saved. Only app launch configuration.
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple

from .platform import is_macos

def get_app_path() -> Path:
    """
    Get the path to the DeskCoach.app bundle.
    
    Returns:
        Path to .app bundle, or None if not running as app
    """
    if not is_macos():
        return None

    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # sys.executable is DeskCoach.app/Contents/MacOS/entry_launcher
        app_path = Path(sys.executable).parent.parent.parent
        if app_path.suffix == '.app':
            return app_path
    
    # Not running as app bundle
    return None


def is_login_item() -> Tuple[bool, str]:
    """
    Check if DeskCoach is in Login Items.
    
    Returns:
        Tuple of (is_enabled, message)
    """
    if not is_macos():
        return False, "Login Items only available on macOS"

    app_path = get_app_path()
    
    if app_path is None:
        return False, "Not running as .app bundle"
    
    try:
        # Use osascript to check Login Items
        script = f'''
tell application "System Events"
    set loginItems to name of every login item
    if loginItems contains "DeskCoach" then
        return "true"
    else
        return "false"
    end if
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            is_enabled = result.stdout.strip() == "true"
            return is_enabled, "OK"
        else:
            return False, f"Error checking: {result.stderr.strip()}"
    
    except subprocess.TimeoutExpired:
        return False, "Timeout checking Login Items"
    except Exception as e:
        return False, f"Error: {e}"


def add_login_item() -> Tuple[bool, str]:
    """
    Add DeskCoach to Login Items.
    
    Returns:
        Tuple of (success, message)
    """
    if not is_macos():
        return False, "Login Items only available on macOS"

    app_path = get_app_path()
    
    if app_path is None:
        return False, "Not running as .app bundle"
    
    if not app_path.exists():
        return False, f"App not found: {app_path}"
    
    try:
        # Use osascript to add to Login Items
        script = f'''
tell application "System Events"
    make new login item at end with properties {{path:"{app_path}", hidden:false, name:"DeskCoach"}}
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return True, "Added to Login Items"
        else:
            error = result.stderr.strip()
            # Check if already exists
            if "already exists" in error.lower() or "duplicate" in error.lower():
                return True, "Already in Login Items"
            return False, f"Error: {error}"
    
    except subprocess.TimeoutExpired:
        return False, "Timeout adding to Login Items"
    except Exception as e:
        return False, f"Error: {e}"


def remove_login_item() -> Tuple[bool, str]:
    """
    Remove DeskCoach from Login Items.
    
    Returns:
        Tuple of (success, message)
    """
    if not is_macos():
        return False, "Login Items only available on macOS"

    app_path = get_app_path()
    
    if app_path is None:
        return False, "Not running as .app bundle"
    
    try:
        # Use osascript to remove from Login Items
        script = '''
tell application "System Events"
    delete (every login item whose name is "DeskCoach")
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return True, "Removed from Login Items"
        else:
            error = result.stderr.strip()
            # Check if doesn't exist
            if "can't get" in error.lower() or "doesn't exist" in error.lower():
                return True, "Not in Login Items"
            return False, f"Error: {error}"
    
    except subprocess.TimeoutExpired:
        return False, "Timeout removing from Login Items"
    except Exception as e:
        return False, f"Error: {e}"


def toggle_login_item() -> Tuple[bool, str]:
    """
    Toggle Login Item status (add if not present, remove if present).
    
    Returns:
        Tuple of (success, message)
    """
    is_enabled, msg = is_login_item()
    
    if "Error" in msg or "Timeout" in msg:
        return False, msg
    
    if is_enabled:
        return remove_login_item()
    else:
        return add_login_item()


def get_login_item_status() -> dict:
    """
    Get Login Item status as a dictionary.
    
    Returns:
        Dictionary with status information
    """
    app_path = get_app_path()
    is_enabled, message = is_login_item()
    
    return {
        "available": app_path is not None,
        "app_path": str(app_path) if app_path else None,
        "enabled": is_enabled,
        "message": message
    }


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage DeskCoach Login Items")
    parser.add_argument("action", choices=["status", "add", "remove", "toggle"],
                       help="Action to perform")
    args = parser.parse_args()
    
    if args.action == "status":
        status = get_login_item_status()
        print(f"Available: {status['available']}")
        print(f"App path: {status['app_path']}")
        print(f"Enabled: {status['enabled']}")
        print(f"Message: {status['message']}")
    
    elif args.action == "add":
        success, message = add_login_item()
        print(f"{'✓' if success else '✗'} {message}")
        sys.exit(0 if success else 1)
    
    elif args.action == "remove":
        success, message = remove_login_item()
        print(f"{'✓' if success else '✗'} {message}")
        sys.exit(0 if success else 1)
    
    elif args.action == "toggle":
        success, message = toggle_login_item()
        print(f"{'✓' if success else '✗'} {message}")
        sys.exit(0 if success else 1)
