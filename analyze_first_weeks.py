#!/usr/bin/env python3
from database import get_db

db = get_db()
history = db.get_portfolio_history(limit=50)
history.reverse()  # Chronological order

print("\n" + "="*70)
print("ANALYZING FIRST WEEKS PERFORMANCE")
print("="*70)

print("\nFirst 15 weeks:")
for i, snapshot in enumerate(history[:15], 1):
    value = snapshot.get('portfolio_value', 0)
    date = snapshot['timestamp'][:10]
    notes = snapshot.get('notes', '')

    if i == 1:
        initial = value
        change_pct = 0
    else:
        prev_value = history[i-2].get('portfolio_value', 0)
        change = value - prev_value
        change_pct = (change / prev_value * 100) if prev_value > 0 else 0

    print(f"Week {i:2d}: {date} - ${value:>12,.0f} ({change_pct:+6.2f}%) - {notes[:50]}")

print("\n" + "="*70)

# Calculate what the return SHOULD be
print("\nLet me check if there's an error in the backtest logic...")
print("Week 1 to Week 2 jump: +91.74% is extremely suspicious")
print("\nPossible issues:")
print("  1. Capital not being reduced when buying stocks (double counting)")
print("  2. Wrong position sizing calculation")
print("  3. Price data error for Week 2")
