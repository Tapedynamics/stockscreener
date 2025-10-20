#!/usr/bin/env python3
"""
Test historical data protection system
"""

from database import get_db
from datetime import datetime

print("\n" + "="*70)
print("TESTING HISTORICAL DATA PROTECTION")
print("="*70)

db = get_db()

# Test 1: Check locked snapshots
history = db.get_portfolio_history(limit=100)
locked = [s for s in history if s.get('is_locked')]

print(f"\nTotal snapshots: {len(history)}")
print(f"Locked snapshots: {len(locked)}")
print(f"Unlocked snapshots: {len(history) - len(locked)}")

# Test 2: Check weekly snapshot status
this_week = db.get_this_week_snapshot()
if this_week:
    print(f"\nThis week's snapshot:")
    print(f"  ID: {this_week['id']}")
    print(f"  Timestamp: {this_week['timestamp']}")
    print(f"  Locked: {this_week['is_locked']}")
    print(f"  Value: ${this_week.get('portfolio_value', 0):,.2f}")
else:
    print("\nNo snapshot exists for this week yet")

# Test 3: Check if we can create new snapshot
can_create, reason = db.can_create_new_snapshot()
print(f"\nCan create new snapshot? {can_create}")
print(f"Reason: {reason}")

# Test 4: Show last 5 snapshots
print(f"\nLast 5 snapshots:")
for i, snapshot in enumerate(history[:5], 1):
    timestamp = snapshot['timestamp']
    value = snapshot.get('portfolio_value', 0)
    locked = "LOCKED" if snapshot.get('is_locked') else "unlocked"
    print(f"  {i}. {timestamp[:16]} - ${value:,.0f} - {locked}")

# Test 5: Check chart data integrity
print(f"\nChart data integrity:")
values = [s.get('portfolio_value') for s in history if s.get('portfolio_value')]
if values:
    print(f"  Min value: ${min(values):,.2f}")
    print(f"  Max value: ${max(values):,.2f}")
    print(f"  First value: ${values[-1]:,.2f}")
    print(f"  Last value: ${values[0]:,.2f}")

print("\n" + "="*70)
print("PROTECTION TEST COMPLETE")
print("="*70 + "\n")
