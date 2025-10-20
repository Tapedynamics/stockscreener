#!/usr/bin/env python3
from database import get_db

db = get_db()
h = db.get_portfolio_history(limit=50)
h.reverse()  # Chronological order

print("\n" + "="*70)
print("PORTFOLIO SIZE ANALYSIS")
print("="*70)

print(f"\nTarget portfolio size: 12 stocks")
print(f"\nWeekly portfolio sizes:\n")

sizes = []
for i, snapshot in enumerate(h, 1):
    stocks = snapshot['total_stocks']
    sizes.append(stocks)
    date = snapshot['timestamp'][:10]
    notes = snapshot.get('notes', '')

    flag = ""
    if stocks < 8:
        flag = " ** LOW **"

    print(f"Week {i:2d} ({date}): {stocks:2d} stocks{flag}")

print("\n" + "="*70)
print(f"Statistics:")
print(f"  Average portfolio size: {sum(sizes)/len(sizes):.1f} stocks")
print(f"  Min: {min(sizes)} stocks")
print(f"  Max: {max(sizes)} stocks")
print(f"  Target: 12 stocks")

weeks_below_10 = len([s for s in sizes if s < 10])
weeks_below_8 = len([s for s in sizes if s < 8])
print(f"\n  Weeks with < 10 stocks: {weeks_below_10}/{len(sizes)} ({weeks_below_10/len(sizes)*100:.1f}%)")
print(f"  Weeks with < 8 stocks:  {weeks_below_8}/{len(sizes)} ({weeks_below_8/len(sizes)*100:.1f}%)")

print("\n" + "="*70)
print("\nPROBLEM IDENTIFIED:")
print("The strategy is TOO RESTRICTIVE:")
print("  1. Sells top 3 stocks (puts them in 2-week cooldown)")
print("  2. Only buys stocks with rank >= 4")
print("  3. Cooldown requires rank >= 9 to re-enter")
print("\nRESULT: Not enough eligible stocks to fill portfolio")
print("="*70 + "\n")
