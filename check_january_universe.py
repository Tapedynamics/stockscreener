#!/usr/bin/env python3
"""
Check which stocks from current Finviz universe would have passed filters in January 2025
Uses Yahoo Finance historical data to verify technical criteria
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from stock_screener import get_finviz_stocks
import os
from dotenv import load_dotenv

load_dotenv()

FINVIZ_URL = os.getenv(
    'FINVIZ_URL',
    "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"
)

print("\n" + "="*70)
print("VERIFICA UNIVERSO GENNAIO 2025 vs OTTOBRE 2025")
print("="*70)

# Get current universe (October)
print("\nFetching current Finviz universe (October 2025)...")
current_universe = get_finviz_stocks(FINVIZ_URL)
print(f"Current universe: {len(current_universe)} stocks")
print(f"Stocks: {', '.join(current_universe)}\n")

# Download historical data for these stocks
print("Downloading historical data (Dec 2024 - Oct 2025)...")
data = yf.download(
    current_universe,
    start='2024-12-01',
    end='2025-10-20',
    progress=False,
    auto_adjust=True
)

if 'Close' in data.columns:
    prices = data['Close']
    volumes = data['Volume']
elif isinstance(data.columns, pd.MultiIndex):
    prices = data['Close']
    volumes = data['Volume']
else:
    prices = data
    volumes = None

print(f"Downloaded {len(prices)} days of data\n")

# Check criteria for January 6, 2025 (first week)
jan_date = pd.Timestamp('2025-01-06')

print("="*70)
print(f"CHECKING FILTERS FOR {jan_date.strftime('%Y-%m-%d')}")
print("="*70)

# Get January 6 data
try:
    jan_idx = prices.index.get_indexer([jan_date], method='nearest')[0]
    jan_prices = prices.iloc[jan_idx]
    jan_volumes = volumes.iloc[jan_idx] if volumes is not None else None

    # Calculate SMA 200 at January 6
    sma_200 = prices.iloc[max(0, jan_idx-200):jan_idx+1].rolling(window=200, min_periods=1).mean().iloc[-1]

    print("\nVerifying technical criteria for each stock:\n")

    passed_criteria = []
    failed_criteria = []

    for ticker in current_universe:
        print(f"{ticker}:")

        checks = []
        passed = True

        # Get January data
        jan_price = jan_prices[ticker] if ticker in jan_prices else None
        jan_vol = jan_volumes[ticker] if jan_volumes is not None and ticker in jan_volumes else None
        jan_sma = sma_200[ticker] if ticker in sma_200 else None

        if jan_price is None:
            print(f"  [SKIP] No data available")
            continue

        # Check 1: Volume > 100K
        if jan_vol is not None:
            if jan_vol > 100000:
                checks.append(f"  Volume: {jan_vol:,.0f} > 100K")
            else:
                checks.append(f"  Volume: {jan_vol:,.0f} < 100K [FAIL]")
                passed = False

        # Check 2: Price > SMA 200
        if jan_sma is not None:
            if jan_price > jan_sma:
                checks.append(f"  Price > SMA200: ${jan_price:.2f} > ${jan_sma:.2f}")
            else:
                checks.append(f"  Price < SMA200: ${jan_price:.2f} < ${jan_sma:.2f} [FAIL]")
                passed = False

        # Check 3: Market cap (get current info as proxy)
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mcap = info.get('marketCap', 0)
            if mcap > 2e9:  # > $2B
                checks.append(f"  Market cap: ${mcap/1e9:.2f}B > $2B")
            else:
                checks.append(f"  Market cap: ${mcap/1e9:.2f}B < $2B [FAIL]")
                passed = False
        except:
            checks.append(f"  Market cap: Unable to verify")

        # Print results
        for check in checks:
            print(check)

        if passed:
            passed_criteria.append(ticker)
            print(f"  [PASS] Would have been in universe\n")
        else:
            failed_criteria.append(ticker)
            print(f"  [FAIL] Would NOT have been in universe\n")

    print("="*70)
    print("SUMMARY")
    print("="*70)

    print(f"\nStocks that would have PASSED filters in January:")
    print(f"  Count: {len(passed_criteria)}/{len(current_universe)}")
    if passed_criteria:
        print(f"  Tickers: {', '.join(passed_criteria)}")

    print(f"\nStocks that would have FAILED filters in January:")
    print(f"  Count: {len(failed_criteria)}/{len(current_universe)}")
    if failed_criteria:
        print(f"  Tickers: {', '.join(failed_criteria)}")

    print(f"\n{'='*70}")
    print("NOTE:")
    print("  - This checks only TECHNICAL criteria (price, volume, SMA200, mcap)")
    print("  - Cannot verify FUNDAMENTAL criteria (EPS growth, margins, ROE)")
    print("  - Those require historical financial statements (not available via API)")
    print("  - Real January universe was likely different")
    print(f"{'='*70}\n")

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
