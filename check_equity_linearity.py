#!/usr/bin/env python3
from database import get_db

db = get_db()
h = db.get_portfolio_history(limit=50)
h.reverse()  # Chronological order

print("\n" + "="*70)
print("EQUITY LINE LINEARITY CHECK")
print("="*70)

print(f"\nTotal weeks: {len(h)}")
print("\nWeekly returns:")

anomalies = []

for i in range(len(h)):
    val = h[i].get('portfolio_value', 0)
    date = h[i]['timestamp'][:10]

    if i == 0:
        print(f"Week {i+1:2d} ({date}): ${val:>12,.0f} (baseline)")
    else:
        prev = h[i-1].get('portfolio_value', 0)
        weekly_change = ((val - prev) / prev * 100) if prev > 0 else 0

        # Flag anomalies (> 20% weekly change)
        flag = ""
        if abs(weekly_change) > 20:
            flag = " ** ANOMALY **"
            anomalies.append({
                'week': i+1,
                'date': date,
                'change_pct': weekly_change,
                'value': val,
                'prev_value': prev
            })

        print(f"Week {i+1:2d} ({date}): ${val:>12,.0f} ({weekly_change:+6.2f}%){flag}")

if anomalies:
    print("\n" + "="*70)
    print(f"WARNING: FOUND {len(anomalies)} ANOMALIES (>20% weekly change)")
    print("="*70)
    for a in anomalies:
        print(f"\nWeek {a['week']} ({a['date']}):")
        print(f"  Previous: ${a['prev_value']:,.0f}")
        print(f"  Current:  ${a['value']:,.0f}")
        print(f"  Change:   {a['change_pct']:+.2f}%")
else:
    print("\n" + "="*70)
    print("OK: No anomalies detected - equity line is linear")
    print("="*70)

# Calculate average weekly return
if len(h) > 1:
    total_return = ((h[-1].get('portfolio_value', 0) - h[0].get('portfolio_value', 0)) / h[0].get('portfolio_value', 1)) * 100
    avg_weekly = total_return / (len(h) - 1)
    print(f"\nTotal return: {total_return:+.2f}%")
    print(f"Average weekly return: {avg_weekly:+.2f}%")

print("\n" + "="*70 + "\n")
