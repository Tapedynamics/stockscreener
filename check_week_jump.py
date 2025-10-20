#!/usr/bin/env python3
from database import get_db

db = get_db()
h = db.get_portfolio_history(limit=50)
h.reverse()  # Chronological order

print("\n" + "="*70)
print("INVESTIGATING WEEK 2 JUMP")
print("="*70)

print("\nWeek 1:")
print(f"  Date: {h[0]['timestamp'][:10]}")
print(f"  Value: ${h[0].get('portfolio_value', 0):,.2f}")
print(f"  Stocks: {h[0]['total_stocks']}")
print(f"  Notes: {h[0].get('notes', '')}")

print("\nWeek 2:")
print(f"  Date: {h[1]['timestamp'][:10]}")
print(f"  Value: ${h[1].get('portfolio_value', 0):,.2f}")
print(f"  Stocks: {h[1]['total_stocks']}")
print(f"  Notes: {h[1].get('notes', '')}")

change = h[1].get('portfolio_value', 0) - h[0].get('portfolio_value', 0)
pct = (change / h[0].get('portfolio_value', 1)) * 100

print(f"\nChange: ${change:,.2f} ({pct:+.2f}%)")

print("\nFirst 5 weeks progression:")
for i in range(min(5, len(h))):
    val = h[i].get('portfolio_value', 0)
    if i == 0:
        print(f"Week {i+1}: ${val:,.2f} (baseline)")
    else:
        prev = h[i-1].get('portfolio_value', 0)
        weekly_change = ((val - prev) / prev * 100) if prev > 0 else 0
        print(f"Week {i+1}: ${val:,.2f} ({weekly_change:+.2f}%)")

print("\n" + "="*70 + "\n")
