#!/usr/bin/env python3
"""
Test notification system independently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import NotificationEngine

def test_notifications():
    """Test if notifications are working."""
    print("Testing notification system...")
    print()
    
    engine = NotificationEngine()
    
    # Test a simple notification
    print("Sending test notification...")
    success = engine.post_notification(
        title="DeskCoach Test",
        message="If you see this, notifications are working!",
        sound="default"
    )
    
    if success:
        print("✅ Notification sent successfully")
    else:
        print("❌ Notification failed")
    
    return success

if __name__ == "__main__":
    success = test_notifications()
    sys.exit(0 if success else 1)
