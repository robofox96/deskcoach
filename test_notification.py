#!/usr/bin/env python3
"""
Test notification posting.

Usage:
    python test_notification.py
"""

from core import NotificationEngine

def main():
    print("Testing DeskCoach notifications...")
    print()
    
    engine = NotificationEngine()
    
    # Test 1: Simple notification
    print("Test 1: Posting simple notification...")
    success = engine.post_with_terminal_notifier(
        title="DeskCoach Test",
        message="This is a test notification from DeskCoach",
        subtitle="Testing"
    )
    
    if success:
        print("✅ Notification posted successfully!")
        print("   Check your notification center to see it.")
    else:
        print("❌ Failed to post notification")
        print("   Make sure terminal-notifier is installed:")
        print("   brew install terminal-notifier")
    
    print()
    
    # Test 2: Posture notification
    print("Test 2: Posting posture notification...")
    success = engine.post_with_terminal_notifier(
        title="Posture Check: Slouching",
        message="Neck 19.5° > 16.4° (73% of last 30s)",
        subtitle=None
    )
    
    if success:
        print("✅ Posture notification posted!")
    else:
        print("❌ Failed to post notification")
    
    print()
    print("Done! Check your notification center.")


if __name__ == "__main__":
    main()
