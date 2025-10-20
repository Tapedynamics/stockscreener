#!/usr/bin/env python3
from database import get_db

db = get_db()
h = db.get_portfolio_history(limit=100)

print("\n" + "="*70)
print("HISTORICAL SNAPSHOTS - TIMELINE VERIFICATION")
print("="*70)

print(f"\nTotal snapshots: {len(h)}")

# Group by month
from collections import defaultdict
months = defaultdict(list)

for snapshot in h:
    timestamp = snapshot['timestamp']
    month = timestamp[:7]  # YYYY-MM
    months[month].append(snapshot)

print(f"\nSnapshots by month:")
for month in sorted(months.keys()):
    snapshots = months[month]
    values = [s.get('portfolio_value', 0) for s in snapshots]
    avg_value = sum(values) / len(values) if values else 0
    print(f"  {month}: {len(snapshots)} snapshots, Avg value: ${avg_value:,.0f}")

print(f"\nFirst 5 snapshots (chronological):")
for i, s in enumerate(h[-5:][::-1], 1):
    print(f"  {i}. {s['timestamp'][:16]}: ${s.get('portfolio_value', 0):,.0f} - {s.get('notes', '')[:40]}")

print(f"\nLast 5 snapshots (chronological):")
for i, s in enumerate(h[:5], 1):
    print(f"  {i}. {s['timestamp'][:16]}: ${s.get('portfolio_value', 0):,.0f} - {s.get('notes', '')[:40]}")

print(f"\nValue progression:")
values = [s.get('portfolio_value', 0) for s in h]
values.reverse()  # Chronological order
if values:
    print(f"  Start: ${values[0]:,.0f} ({h[-1]['timestamp'][:10]})")
    print(f"  Peak:  ${max(values):,.0f}")
    print(f"  End:   ${values[-1]:,.0f} ({h[0]['timestamp'][:10]})")
    total_return = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
    print(f"  Return: {total_return:+.2f}%")

print("\n" + "="*70 + "\n")
