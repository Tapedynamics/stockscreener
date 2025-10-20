#!/usr/bin/env python3
"""
Calculate real historical performance of current portfolio
Downloads actual stock prices from Yahoo Finance
"""

import yfinance as yf
from database import get_db
from datetime import datetime
import pandas as pd

def calculate_portfolio_performance():
    """Calculate real performance from Jan 1, 2025 to today"""

    # Get latest portfolio
    db = get_db()
    portfolio = db.get_latest_portfolio()

    if not portfolio:
        print("No portfolio found in database")
        return

    # Get all tickers
    all_tickers = portfolio['take_profit'] + portfolio['hold'] + portfolio['buffer']

    print("\n" + "="*70)
    print("REAL PORTFOLIO PERFORMANCE CALCULATION")
    print("="*70)
    print(f"\nPortfolio: {len(all_tickers)} stocks")
    print(f"Tickers: {', '.join(all_tickers)}")
    print(f"\nCalculating performance from January 1, 2025 to {datetime.now().strftime('%B %d, %Y')}")
    print("="*70 + "\n")

    # Download historical data
    start_date = "2025-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    print("Downloading historical price data from Yahoo Finance...")

    # Download data for all tickers
    data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)

    if data.empty:
        print("ERROR: No data downloaded. Check tickers or date range.")
        return

    # Use adjusted close prices (auto_adjust=True means 'Close' is already adjusted)
    prices = data['Close']

    # Handle single ticker case (returns Series instead of DataFrame)
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(all_tickers[0])

    print(f"Downloaded {len(prices)} days of price data")

    # Calculate individual stock returns
    print("\n" + "-"*70)
    print("INDIVIDUAL STOCK PERFORMANCE (YTD)")
    print("-"*70)

    individual_returns = {}
    for ticker in all_tickers:
        if ticker in prices.columns:
            first_price = prices[ticker].dropna().iloc[0]
            last_price = prices[ticker].dropna().iloc[-1]
            stock_return = ((last_price - first_price) / first_price) * 100
            individual_returns[ticker] = stock_return

            print(f"{ticker:6s} | ${first_price:8.2f} -> ${last_price:8.2f} | {stock_return:+7.2f}%")
        else:
            print(f"{ticker:6s} | NO DATA AVAILABLE")
            individual_returns[ticker] = 0

    # Calculate equal-weighted portfolio return
    print("\n" + "-"*70)
    print("PORTFOLIO PERFORMANCE (Equal-Weighted)")
    print("-"*70)

    # Calculate daily returns for each stock
    daily_returns = prices.pct_change()

    # Equal-weighted portfolio: average daily return across all stocks
    portfolio_daily_returns = daily_returns.mean(axis=1)

    # Calculate cumulative return
    portfolio_cumulative = (1 + portfolio_daily_returns).cumprod()

    # Total return
    total_return = (portfolio_cumulative.iloc[-1] - 1) * 100

    # Assuming $150,000 initial investment
    initial_value = 150000
    final_value = initial_value * (1 + total_return/100)
    gain = final_value - initial_value

    print(f"\nInitial Investment: ${initial_value:,.2f}")
    print(f"Final Value:        ${final_value:,.2f}")
    print(f"Total Gain:         ${gain:,.2f}")
    print(f"Total Return:       {total_return:+.2f}%")

    # Calculate average stock return
    avg_stock_return = sum(individual_returns.values()) / len(individual_returns)
    print(f"\nAverage Stock Return: {avg_stock_return:+.2f}%")

    # Best and worst performers
    best_stock = max(individual_returns, key=individual_returns.get)
    worst_stock = min(individual_returns, key=individual_returns.get)

    print(f"\nBest Performer:  {best_stock} ({individual_returns[best_stock]:+.2f}%)")
    print(f"Worst Performer: {worst_stock} ({individual_returns[worst_stock]:+.2f}%)")

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")

    return {
        'total_return': total_return,
        'initial_value': initial_value,
        'final_value': final_value,
        'gain': gain,
        'individual_returns': individual_returns,
        'best_stock': (best_stock, individual_returns[best_stock]),
        'worst_stock': (worst_stock, individual_returns[worst_stock])
    }


if __name__ == '__main__':
    try:
        results = calculate_portfolio_performance()
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nMake sure yfinance is installed:")
        print("  pip install yfinance")
