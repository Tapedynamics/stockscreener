#!/usr/bin/env python3
"""
Test what would happen if we ran screening today vs last week (Oct 13)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from database import get_db

# Universe
UNIVERSE = [
    'NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
    'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ',
    'NVDA', 'AMD', 'PLTR', 'COIN', 'MSTR', 'TSLA', 'META',
    'AMZN', 'GOOGL', 'MSFT', 'AAPL', 'NFLX', 'CRM', 'UBER', 'SHOP',
    'SQ', 'PYPL', 'ADBE', 'NOW', 'SNOW', 'DDOG', 'NET', 'CRWD',
    'ZS', 'OKTA', 'PANW', 'FTNT', 'CVNA', 'RIVN', 'LCID'
]

def calculate_momentum(prices, date, lookback_days=30):
    """Calculate 30-day momentum"""
    try:
        current_idx = prices.index.get_indexer([date], method='nearest')[0]
        lookback_idx = max(0, current_idx - lookback_days)

        current_prices = prices.iloc[current_idx]
        past_prices = prices.iloc[lookback_idx]

        returns = ((current_prices - past_prices) / past_prices * 100).dropna()
        ranked = returns.sort_values(ascending=False)

        return ranked
    except Exception as e:
        print(f"Error: {e}")
        return pd.Series()

print("\n" + "="*70)
print("SCREENING COMPARISON: Oct 13 (Week 41) vs Today (Oct 20)")
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

# Download recent data
print("\nDownloading latest price data...")
data = yf.download(UNIVERSE, start='2025-09-01', end='2025-10-21', progress=False, auto_adjust=True)

if 'Close' in data.columns:
    prices = data['Close']
elif isinstance(data.columns, pd.MultiIndex):
    prices = data['Close']
else:
    prices = data

# Calculate momentum for Oct 13
oct_13 = pd.Timestamp('2025-10-13')
momentum_oct13 = calculate_momentum(prices, oct_13)
top15_oct13 = momentum_oct13.head(15).index.tolist()

print(f"\nTop 15 on Oct 13:")
for i, ticker in enumerate(top15_oct13, 1):
    mom = momentum_oct13[ticker]
    in_portfolio = "✓" if ticker in all_current else " "
    print(f"  {i:2d}. {ticker:6s} {mom:+6.1f}%  {in_portfolio}")

# Calculate momentum for today
today = pd.Timestamp('2025-10-20')
momentum_today = calculate_momentum(prices, today)
top15_today = momentum_today.head(15).index.tolist()

print(f"\nTop 15 TODAY (Oct 20):")
for i, ticker in enumerate(top15_today, 1):
    mom = momentum_today[ticker]
    in_old_top15 = "→" if ticker in top15_oct13 else "NEW"
    in_portfolio = "✓" if ticker in all_current else " "
    print(f"  {i:2d}. {ticker:6s} {mom:+6.1f}%  {in_old_top15:3s}  {in_portfolio}")

# Analysis
print("\n" + "="*70)
print("CHANGES ANALYSIS")
print("="*70)

# Stocks that left top 15
left_top15 = [t for t in top15_oct13 if t not in top15_today]
print(f"\nStocks that LEFT top 15: {len(left_top15)}")
for ticker in left_top15:
    in_portfolio = "⚠️ IN PORTFOLIO" if ticker in all_current else ""
    old_rank = top15_oct13.index(ticker) + 1
    print(f"  - {ticker} (was rank #{old_rank}) {in_portfolio}")

# New stocks in top 15
entered_top15 = [t for t in top15_today if t not in top15_oct13]
print(f"\nStocks that ENTERED top 15: {len(entered_top15)}")
for ticker in entered_top15:
    new_rank = top15_today.index(ticker) + 1
    print(f"  + {ticker} (now rank #{new_rank})")

# Stability
stability = len([t for t in top15_oct13 if t in top15_today])
print(f"\nStability: {stability}/15 stocks remained in top 15 ({stability/15*100:.1f}%)")

# Portfolio impact
would_sell = [t for t in all_current if t not in top15_today]
print(f"\nWould SELL from portfolio: {len(would_sell)} stocks")
for ticker in would_sell:
    print(f"  - {ticker} (out of top 15)")

print(f"\nWould BUY to fill portfolio: {len(would_sell)} stocks")
candidates = [t for t in top15_today if t not in all_current][:len(would_sell)]
for ticker in candidates:
    rank = top15_today.index(ticker) + 1
    print(f"  + {ticker} (rank #{rank})")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

turnover_rate = len(would_sell) / len(all_current) * 100
print(f"\nTurnover rate: {len(would_sell)}/{len(all_current)} stocks = {turnover_rate:.1f}%")

if turnover_rate > 50:
    print("\n⚠️  HIGH TURNOVER - More than 50% of portfolio would change")
    print("This is typical for momentum strategies in volatile markets.")
elif turnover_rate > 30:
    print("\n📊 MODERATE TURNOVER - 30-50% of portfolio would change")
    print("Normal for weekly momentum rotation.")
else:
    print("\n✓ LOW TURNOVER - Less than 30% of portfolio would change")
    print("Stable market conditions.")

print(f"\nTop 15 stability: {100-stability/15*100:.1f}% turnover")
print("="*70 + "\n")
