#!/usr/bin/env python3
"""
Quick performance check for latest screener results
"""

import yfinance as yf
from datetime import datetime
import pandas as pd

# Latest screener results
tickers = ['NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
           'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ']

print("\n" + "="*70)
print("PORTFOLIO PERFORMANCE - Latest Screener Results")
print("="*70)
print(f"\nPortfolio: {len(tickers)} stocks")
print(f"Period: January 1, 2024 to {datetime.now().strftime('%B %d, %Y')}")
print("\nTickers:")
print(f"  Take Profit: NXT, JBHT, SCCO")
print(f"  Hold: MU, NEE, AMAT, CXT, CAT, AES, XEL, ELAN, SR, ESAB")
print(f"  Buffer: TXRH, JNJ")
print("="*70 + "\n")

# Download data
print("Downloading price data from Yahoo Finance...")
start_date = "2024-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

try:
    data = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)

    if data.empty:
        print("ERROR: No data downloaded")
        exit(1)

    # Handle both single and multiple tickers
    if 'Close' in data.columns:
        prices = data['Close']
    elif isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data

    print(f"Downloaded {len(prices)} days of data\n")

    print("-"*70)
    print("INDIVIDUAL STOCK PERFORMANCE (YTD 2025)")
    print("-"*70)
    print(f"{'Ticker':<8} {'Start Price':>12} {'Current Price':>15} {'Return':>10}")
    print("-"*70)

    returns = {}
    for ticker in tickers:
        try:
            if ticker in prices.columns:
                stock_prices = prices[ticker].dropna()
                if len(stock_prices) > 0:
                    first_price = stock_prices.iloc[0]
                    last_price = stock_prices.iloc[-1]
                    stock_return = ((last_price - first_price) / first_price) * 100
                    returns[ticker] = stock_return
                    print(f"{ticker:<8} ${first_price:>11.2f} ${last_price:>14.2f} {stock_return:>9.2f}%")
                else:
                    print(f"{ticker:<8} {'NO DATA':>11} {'NO DATA':>14} {'N/A':>10}")
                    returns[ticker] = 0
            else:
                print(f"{ticker:<8} {'NOT FOUND':>11} {'NOT FOUND':>14} {'N/A':>10}")
                returns[ticker] = 0
        except Exception as e:
            print(f"{ticker:<8} ERROR: {str(e)}")
            returns[ticker] = 0

    print("-"*70)

    # Calculate portfolio metrics
    valid_returns = [r for r in returns.values() if r != 0]
    if valid_returns:
        avg_return = sum(valid_returns) / len(valid_returns)

        print("\nPORTFOLIO SUMMARY (Equal-Weighted)")
        print("-"*70)

        initial_investment = 150000
        investment_per_stock = initial_investment / len(tickers)

        total_value = 0
        for ticker, ret in returns.items():
            stock_value = investment_per_stock * (1 + ret/100)
            total_value += stock_value

        total_gain = total_value - initial_investment
        total_return = (total_gain / initial_investment) * 100

        print(f"Initial Investment:   ${initial_investment:>12,.2f}")
        print(f"Current Value:        ${total_value:>12,.2f}")
        print(f"Total Gain/Loss:      ${total_gain:>12,.2f}")
        print(f"Total Return:         {total_return:>12.2f}%")
        print(f"Average Stock Return: {avg_return:>12.2f}%")

        # Best and worst
        best_ticker = max(returns, key=returns.get)
        worst_ticker = min(returns, key=returns.get)

        print(f"\nBest Performer:  {best_ticker} ({returns[best_ticker]:+.2f}%)")
        print(f"Worst Performer: {worst_ticker} ({returns[worst_ticker]:+.2f}%)")

        print("\n" + "="*70)
    else:
        print("\nERROR: No valid data retrieved")

except Exception as e:
    print(f"\nERROR: {e}")
    print("\nMake sure yfinance is installed: pip install yfinance")

print()
