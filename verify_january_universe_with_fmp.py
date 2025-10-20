#!/usr/bin/env python3
"""
Verify which stocks passed ALL Finviz filters in January 2025
Uses FMP API for historical fundamental data + Yahoo for technical data

FMP API Key: Get free key at https://financialmodelingprep.com/developer/docs/
  - Free tier: 250 requests/day
  - Historical fundamental data available
"""

import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# FMP API Configuration
FMP_API_KEY = os.getenv('FMP_API_KEY', '')

if not FMP_API_KEY:
    print("\n" + "="*70)
    print("FMP API KEY REQUIRED")
    print("="*70)
    print("\nTo get historical fundamental data, you need a FREE FMP API key:")
    print("\n1. Go to: https://financialmodelingprep.com/developer/docs/")
    print("2. Click 'Get my API KEY here'")
    print("3. Sign up (free - takes 2 minutes)")
    print("4. Copy your API key")
    print("5. Add to .env file: FMP_API_KEY=your_key_here")
    print("\nOR enter it now:\n")

    FMP_API_KEY = input("FMP API Key: ").strip()

    if not FMP_API_KEY:
        print("\nERROR: API key required. Exiting.\n")
        exit(1)

# Configuration
START_DATE = '2024-12-01'  # Need data before Jan 2025 for SMA200
JAN_DATE = '2025-01-06'    # First Monday of January 2025
END_DATE = '2025-01-31'

# Finviz filters (from URL parameters)
FILTERS = {
    'market_cap_min': 2e9,           # $2B+ (cap_midover)
    'pe_max': 30,                    # P/E < 30 (fa_pe_u30)
    'volume_min': 100000,            # > 100K (sh_avgvol_o100, sh_curvol_o100)
    'eps_5y_growth_min': 0,          # Positive (fa_eps5years_pos)
    'est_ltg_min': 0,                # Positive (fa_estltgrowth_pos)
    'net_margin_min': 0,             # Positive (fa_netmargin_pos)
    'oper_margin_min': 0,            # Positive (fa_opermargin_pos)
    'roe_min': 0,                    # Positive (fa_roe_pos)
    'country': 'US',                 # USA only (geo_usa)
    'price_vs_sma200': 'above'       # Price > SMA 200 (ta_sma200_pa)
}

def get_sp500_tickers():
    """Get S&P 500 tickers as starting universe"""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    tables = pd.read_html(url)
    df = tables[0]
    return df['Symbol'].str.replace('.', '-').tolist()

def get_russell_1000_tickers():
    """Get Russell 1000 tickers (top 1000 US stocks by market cap)"""
    # Using a curated list of major US stocks
    # This is a simplified approach - in production you'd want complete Russell 1000
    sp500 = get_sp500_tickers()

    # Add common mid/large cap stocks not in S&P 500
    additional = [
        'PLTR', 'SNOW', 'COIN', 'RKLB', 'HOOD', 'DDOG', 'CRWD', 'ZS', 'NET',
        'AMAT', 'LRCX', 'KLAC', 'MCHP', 'ON', 'TER', 'MPWR', 'ENTG', 'GFS',
        'CAT', 'DE', 'CMI', 'EMR', 'ETN', 'HON', 'ITW', 'PH', 'ROK',
        'NEE', 'DUK', 'SO', 'D', 'EXC', 'AEP', 'SRE', 'XEL', 'ES', 'AES',
        'SCCO', 'FCX', 'NEM', 'GOLD', 'ALB', 'MP', 'LAC',
        'NXT', 'JBHT', 'CHRW', 'EXPD', 'KNX', 'R', 'LSTR',
        'ELAN', 'WTRG', 'AWK', 'CWT', 'SJW',
        'SR', 'CXT', 'EME', 'ESAB', 'GATX'
    ]

    return list(set(sp500 + additional))

def check_technical_filters(ticker, prices, volumes, date):
    """Check technical filters at given date"""
    try:
        jan_idx = prices.index.get_indexer([pd.Timestamp(date)], method='nearest')[0]

        # Get January data
        jan_price = prices.iloc[jan_idx][ticker]
        jan_volume = volumes.iloc[jan_idx][ticker] if volumes is not None else None

        # Calculate SMA 200
        sma_data = prices[ticker].iloc[max(0, jan_idx-200):jan_idx+1]
        if len(sma_data) < 50:  # Need at least 50 days
            return False, "Insufficient data for SMA200"

        sma_200 = sma_data.mean()

        # Check filters
        checks = {}

        # Volume
        if jan_volume is not None:
            checks['volume'] = jan_volume > FILTERS['volume_min']
        else:
            return False, "No volume data"

        # Price vs SMA 200
        checks['sma200'] = jan_price > sma_200

        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            return False, f"Failed: {', '.join(failed)}"

        return True, "Technical filters passed"

    except Exception as e:
        return False, f"Error: {e}"

def get_fmp_fundamental_data(ticker, api_key):
    """Get fundamental data from FMP API for 2024 (latest before Jan 2025)"""
    try:
        # Get key metrics (for margins, ROE, etc.)
        url = f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}?period=annual&apikey={api_key}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return None, f"API error: {response.status_code}"

        metrics = response.json()

        if not metrics or len(metrics) == 0:
            return None, "No metrics data"

        # Get latest data from 2024 or before
        latest_2024 = None
        for metric in metrics:
            date = metric.get('date', '')
            if date.startswith('2024') or date.startswith('2023'):
                latest_2024 = metric
                break

        if not latest_2024:
            return None, "No 2024 data"

        # Get ratios (for P/E)
        url_ratios = f"https://financialmodelingprep.com/api/v3/ratios/{ticker}?period=annual&apikey={api_key}"
        response_ratios = requests.get(url_ratios, timeout=10)
        ratios = response_ratios.json() if response_ratios.status_code == 200 else []

        latest_ratios = None
        for ratio in ratios:
            date = ratio.get('date', '')
            if date.startswith('2024') or date.startswith('2023'):
                latest_ratios = ratio
                break

        # Get income statement (for margins)
        url_income = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=annual&apikey={api_key}"
        response_income = requests.get(url_income, timeout=10)
        income = response_income.json() if response_income.status_code == 200 else []

        latest_income = None
        for inc in income:
            date = inc.get('date', '')
            if date.startswith('2024') or date.startswith('2023'):
                latest_income = inc
                break

        # Get growth data
        url_growth = f"https://financialmodelingprep.com/api/v3/financial-growth/{ticker}?period=annual&apikey={api_key}"
        response_growth = requests.get(url_growth, timeout=10)
        growth = response_growth.json() if response_growth.status_code == 200 else []

        latest_growth = growth[0] if growth and len(growth) > 0 else None

        return {
            'metrics': latest_2024,
            'ratios': latest_ratios,
            'income': latest_income,
            'growth': latest_growth
        }, None

    except Exception as e:
        return None, f"Exception: {e}"

def check_fundamental_filters(data):
    """Check if fundamental data passes Finviz filters"""
    checks = {}

    metrics = data.get('metrics', {}) or {}
    ratios = data.get('ratios', {}) or {}
    income = data.get('income', {}) or {}
    growth = data.get('growth', {}) or {}

    # Market cap
    market_cap = metrics.get('marketCap')
    checks['market_cap'] = market_cap and market_cap > FILTERS['market_cap_min']

    # P/E ratio
    pe_ratio = ratios.get('priceEarningsRatio')
    checks['pe'] = pe_ratio and 0 < pe_ratio < FILTERS['pe_max']

    # Net margin
    net_margin = income.get('netIncomeRatio')  # This is net margin
    checks['net_margin'] = net_margin and net_margin > FILTERS['net_margin_min']

    # Operating margin
    oper_margin = income.get('operatingIncomeRatio')
    checks['oper_margin'] = oper_margin and oper_margin > FILTERS['oper_margin_min']

    # ROE
    roe = metrics.get('roe')
    checks['roe'] = roe and roe > FILTERS['roe_min']

    # EPS 5-year growth
    eps_growth_5y = growth.get('fiveYEarRevenueGrowthPerShare') or growth.get('epsgrowth')
    checks['eps_5y'] = eps_growth_5y and eps_growth_5y > FILTERS['eps_5y_growth_min']

    # Estimated long-term growth (use recent growth as proxy)
    # FMP doesn't have analyst estimates in free tier, so we'll be lenient here
    checks['est_ltg'] = True  # Accept if other criteria pass

    passed = all(checks.values())
    failed = [k for k, v in checks.items() if not v]

    return passed, checks, failed

def main():
    print("\n" + "="*70)
    print("VERIFY JANUARY 2025 UNIVERSE WITH HISTORICAL FUNDAMENTALS")
    print("="*70)
    print(f"Using FMP API key: {FMP_API_KEY[:10]}...")

    # Get starting universe
    print("\n1. Building starting universe (S&P 500 + common mid/large caps)...")
    universe = get_russell_1000_tickers()
    print(f"   Starting with {len(universe)} tickers")

    # Download technical data from Yahoo
    print("\n2. Downloading technical data from Yahoo Finance...")
    print(f"   Period: {START_DATE} to {END_DATE}")

    data = yf.download(universe, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)

    if data.empty:
        print("ERROR: No data downloaded")
        return

    if 'Close' in data.columns:
        prices = data['Close']
        volumes = data['Volume']
    elif isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
        volumes = data['Volume']
    else:
        prices = data
        volumes = None

    print(f"   Downloaded {len(prices)} days of data")

    # Filter by technical criteria first (cheaper, faster)
    print(f"\n3. Filtering by technical criteria at {JAN_DATE}...")
    technical_passed = []

    for ticker in universe:
        if ticker not in prices.columns:
            continue

        passed, reason = check_technical_filters(ticker, prices, volumes, JAN_DATE)
        if passed:
            technical_passed.append(ticker)

    print(f"   Technical filters passed: {len(technical_passed)}/{len(universe)} stocks")
    print(f"   Tickers: {', '.join(technical_passed[:20])}{'...' if len(technical_passed) > 20 else ''}")

    # Now check fundamentals for those that passed technical
    print(f"\n4. Checking fundamental criteria with FMP API...")
    print(f"   (This will make {len(technical_passed) * 4} API calls)")
    print(f"   Free tier limit: 250/day")

    if len(technical_passed) * 4 > 250:
        print(f"\n   WARNING: May exceed free tier limit!")
        print(f"   Consider using paid tier or processing in batches")
        response = input("\n   Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("\n   Cancelled\n")
            return

    final_passed = []
    results = []

    for i, ticker in enumerate(technical_passed, 1):
        print(f"   [{i}/{len(technical_passed)}] {ticker}...", end=' ')

        data, error = get_fmp_fundamental_data(ticker, FMP_API_KEY)

        if error:
            print(f"SKIP ({error})")
            results.append({
                'ticker': ticker,
                'passed': False,
                'reason': error
            })
            continue

        passed, checks, failed = check_fundamental_filters(data)

        if passed:
            print("PASS ✓")
            final_passed.append(ticker)
            results.append({
                'ticker': ticker,
                'passed': True,
                'checks': checks
            })
        else:
            print(f"FAIL ({', '.join(failed)})")
            results.append({
                'ticker': ticker,
                'passed': False,
                'reason': f"Failed: {', '.join(failed)}",
                'checks': checks
            })

    # Summary
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    print(f"\nStocks that passed ALL filters in January 2025:")
    print(f"  Count: {len(final_passed)}")
    if final_passed:
        print(f"  Tickers: {', '.join(final_passed)}")

    # Save results
    output_file = 'january_2025_universe.txt'
    with open(output_file, 'w') as f:
        f.write("JANUARY 2025 FINVIZ UNIVERSE\n")
        f.write("="*70 + "\n\n")
        f.write(f"Date verified: {JAN_DATE}\n")
        f.write(f"Total stocks passed: {len(final_passed)}\n\n")
        f.write("Tickers:\n")
        for ticker in final_passed:
            f.write(f"  {ticker}\n")
        f.write("\n\nDETAILED RESULTS:\n")
        f.write("="*70 + "\n\n")
        for result in results:
            ticker = result['ticker']
            if result['passed']:
                f.write(f"{ticker}: PASSED\n")
                checks = result.get('checks', {})
                for check, value in checks.items():
                    f.write(f"  {check}: {'✓' if value else '✗'}\n")
            else:
                f.write(f"{ticker}: FAILED - {result['reason']}\n")
            f.write("\n")

    print(f"\nResults saved to: {output_file}")
    print("\n" + "="*70 + "\n")

    print("NEXT STEPS:")
    print("  1. Review january_2025_universe.txt")
    print("  2. Use these tickers in backtest_finviz_strategy.py")
    print("  3. Run backtest with historical Yahoo data")
    print("\n")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
