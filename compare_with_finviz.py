#!/usr/bin/env python3
"""
Compare current Finviz ranking with Oct 13 portfolio
"""

from stock_screener import get_finviz_stocks
from database import get_db
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Finviz URL from environment
FINVIZ_URL = os.getenv(
    'FINVIZ_URL',
    'https://finviz.com/screener.ashx?v=111&f=cap_midunder,fa_eps5years_pos,fa_epsyoy_pos,fa_grossmargin_pos,fa_salesqoq_pos,sh_avgvol_o300,sh_price_o5,ta_perf_52w50o&ft=4&o=-change'
)

print("\n" + "="*70)
print("LIVE COMPARISON: Portfolio (Oct 13) vs Finviz TODAY")
print("="*70)

# Get current portfolio (Oct 13)
db = get_db()
current = db.get_latest_portfolio()

print("\nCurrent Portfolio (Oct 13, 2025):")
print(f"  Take Profit: {', '.join(current['take_profit'])}")
print(f"  Hold: {', '.join(current['hold'])}")
print(f"  Buffer: {', '.join(current['buffer'])}")

all_current = current['take_profit'] + current['hold'] + current['buffer']
print(f"\n  Total: {len(all_current)} stocks")

print(f"\nFetching live data from Finviz...")
print(f"URL: {FINVIZ_URL[:80]}...")

# Get current top 15 from Finviz
try:
    finviz_stocks = get_finviz_stocks(FINVIZ_URL)
    top15_today = finviz_stocks[:15]

    print(f"\nTop 15 on Finviz TODAY:")
    for i, ticker in enumerate(top15_today, 1):
        in_portfolio = "[IN PORTFOLIO]" if ticker in all_current else ""
        print(f"  {i:2d}. {ticker:6s} {in_portfolio}")

    # Analysis
    print("\n" + "="*70)
    print("CHANGES ANALYSIS")
    print("="*70)

    # Stocks in portfolio but OUT of top 15 (would be SOLD)
    would_sell = [t for t in all_current if t not in top15_today]
    print(f"\nWould SELL from portfolio: {len(would_sell)} stocks")
    for ticker in would_sell:
        print(f"  - {ticker} (no longer in top 15)")

    # Stocks in top 15 but NOT in portfolio (would be BOUGHT)
    would_buy = [t for t in top15_today if t not in all_current][:len(would_sell)]
    print(f"\nWould BUY to fill portfolio: {len(would_buy)} stocks")
    for ticker in would_buy:
        rank = top15_today.index(ticker) + 1
        print(f"  + {ticker} (rank #{rank})")

    # Stocks that would STAY
    would_stay = [t for t in all_current if t in top15_today]
    print(f"\nWould STAY in portfolio: {len(would_stay)} stocks")
    for ticker in would_stay:
        rank = top15_today.index(ticker) + 1
        print(f"  = {ticker} (rank #{rank})")

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)

    turnover_rate = len(would_sell) / len(all_current) * 100
    stability_rate = len(would_stay) / len(all_current) * 100

    print(f"\nTurnover: {len(would_sell)}/{len(all_current)} stocks = {turnover_rate:.1f}%")
    print(f"Stability: {len(would_stay)}/{len(all_current)} stocks = {stability_rate:.1f}%")

    if turnover_rate > 50:
        print("\n[HIGH TURNOVER] More than 50% would change")
        print("This is NORMAL for momentum strategies in volatile markets.")
        print("Momentum indicators change quickly (30-day window).")
    elif turnover_rate > 30:
        print("\n[MODERATE TURNOVER] 30-50% would change")
        print("Normal weekly rotation for momentum strategies.")
    else:
        print("\n[LOW TURNOVER] Less than 30% would change")
        print("Stable market conditions.")

    print("\nREASONS FOR HIGH TURNOVER:")
    print("  1. Momentum = 30-day performance (fast-changing)")
    print("  2. 7 days passed since last snapshot (Oct 13 -> Oct 20)")
    print("  3. Market volatility affects rankings quickly")
    print("  4. Trailing stop @ 15% may have triggered for some stocks")

    print("\n" + "="*70 + "\n")

except Exception as e:
    print(f"\nError fetching Finviz data: {e}")
    import traceback
    traceback.print_exc()
