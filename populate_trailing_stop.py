#!/usr/bin/env python3
"""
Populate database with trailing stop strategy backtest
Maintains 12-stock portfolio with 15% trailing stop loss
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from database import get_db

# Configuration
INITIAL_CAPITAL = 150000
PORTFOLIO_SIZE = 12
TRAILING_STOP_PERCENT = 0.15  # 15% trailing stop

START_DATE = '2025-01-01'
END_DATE = '2025-10-19'

# Universe of tickers
UNIVERSE = [
    'NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
    'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ',
    'NVDA', 'AMD', 'PLTR', 'COIN', 'MSTR', 'TSLA', 'META',
    'AMZN', 'GOOGL', 'MSFT', 'AAPL', 'NFLX', 'CRM', 'UBER', 'SHOP',
    'SQ', 'PYPL', 'ADBE', 'NOW', 'SNOW', 'DDOG', 'NET', 'CRWD',
    'ZS', 'OKTA', 'PANW', 'FTNT', 'CVNA', 'RIVN', 'LCID'
]

def calculate_momentum(prices, date, lookback_days=30):
    """Calculate 30-day momentum at given date"""
    try:
        current_idx = prices.index.get_indexer([date], method='nearest')[0]
        lookback_idx = max(0, current_idx - lookback_days)

        current_prices = prices.iloc[current_idx]
        past_prices = prices.iloc[lookback_idx]

        returns = ((current_prices - past_prices) / past_prices * 100).dropna()
        ranked = returns.sort_values(ascending=False)

        return ranked
    except Exception as e:
        print(f"Error calculating momentum for {date}: {e}")
        return pd.Series()

def populate_database_trailing_stop():
    """Run trailing stop backtest and populate database"""

    db = get_db()

    print("\n" + "="*70)
    print("TRAILING STOP STRATEGY BACKTEST")
    print("="*70)
    print(f"Portfolio size: {PORTFOLIO_SIZE} stocks")
    print(f"Trailing stop: {TRAILING_STOP_PERCENT*100:.0f}%")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.0f}")

    # Download price data
    print(f"\nDownloading data for {len(UNIVERSE)} tickers...")
    data = yf.download(UNIVERSE, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)

    if data.empty:
        print("ERROR: No data downloaded")
        return

    if 'Close' in data.columns:
        prices = data['Close']
    elif isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data

    print(f"Downloaded {len(prices)} days of data")

    # Generate weekly dates (Mondays)
    date_range = pd.date_range(start=START_DATE, end=END_DATE, freq='W-MON')
    weekly_dates = [d for d in date_range if d in prices.index or
                    (d + timedelta(days=1)) in prices.index or
                    (d + timedelta(days=2)) in prices.index]

    print(f"Will create {len(weekly_dates)} weekly snapshots\n")

    # Strategy state
    portfolio = []
    capital = INITIAL_CAPITAL
    shares_held = {}  # {ticker: shares}
    highest_prices = {}  # {ticker: highest_price_since_entry}

    snapshots_created = 0
    total_sells = 0
    total_buys = 0
    stop_loss_sells = 0

    for week_num, date in enumerate(weekly_dates, 1):
        print(f"Week {week_num}/{len(weekly_dates)}: {date.strftime('%Y-%m-%d')}")

        # Calculate momentum
        momentum = calculate_momentum(prices, date)

        if len(momentum) == 0:
            print("  No momentum data, skipping")
            continue

        top_15 = momentum.head(15).index.tolist()

        # Get current prices
        current_idx = prices.index.get_indexer([date], method='nearest')[0]
        current_prices = prices.iloc[current_idx]

        if week_num == 1:
            # First week - buy top 12
            portfolio = top_15[:PORTFOLIO_SIZE]
            position_size = capital / len(portfolio)

            for ticker in portfolio:
                price = current_prices[ticker]
                shares = position_size / price
                shares_held[ticker] = shares
                highest_prices[ticker] = price  # Initialize trailing stop
                capital -= position_size

            total_buys += len(portfolio)

            # Calculate portfolio value
            portfolio_value = capital + sum(shares_held[t] * current_prices[t] for t in portfolio)

            # Save snapshot
            db.save_portfolio_snapshot(
                take_profit=portfolio[:3],
                hold=portfolio[3:10] if len(portfolio) > 3 else [],
                buffer=portfolio[10:] if len(portfolio) > 10 else [],
                notes=f'Week {week_num}: Initial portfolio ({len(portfolio)} stocks)',
                portfolio_value=portfolio_value,
                is_locked=True,
                timestamp=date
            )

            snapshots_created += 1
            print(f"  Initial portfolio: {len(portfolio)} stocks, Value: ${portfolio_value:,.2f}")

        else:
            to_sell = []

            # Check trailing stops and top 15 membership
            for ticker in list(portfolio):
                current_price = current_prices[ticker]

                # Update highest price if new high
                if current_price > highest_prices[ticker]:
                    highest_prices[ticker] = current_price

                # Calculate stop price
                stop_price = highest_prices[ticker] * (1 - TRAILING_STOP_PERCENT)

                # Sell if:
                # 1. Price hit trailing stop
                # 2. Out of top 15
                if current_price < stop_price:
                    to_sell.append((ticker, 'trailing_stop', current_price, stop_price))
                    stop_loss_sells += 1
                elif ticker not in top_15:
                    to_sell.append((ticker, 'out_of_top15', current_price, None))

            # Execute sells
            for ticker, reason, price, stop_price in to_sell:
                if ticker in shares_held:
                    shares = shares_held[ticker]
                    value = shares * price
                    capital += value
                    del shares_held[ticker]
                    del highest_prices[ticker]
                    portfolio.remove(ticker)
                    total_sells += 1

                    # Record sale
                    db.record_sale(ticker, reason, 0)

                    if reason == 'trailing_stop':
                        print(f"  SELL {ticker}: ${price:.2f} < ${stop_price:.2f} (stop)")
                    else:
                        print(f"  SELL {ticker}: out of top 15")

            # Buy to fill portfolio
            slots_to_fill = PORTFOLIO_SIZE - len(portfolio)

            if slots_to_fill > 0:
                # Buy best stocks from top 15 that we don't have
                candidates = [t for t in top_15 if t not in portfolio]
                to_buy = candidates[:slots_to_fill]

                if to_buy:
                    position_size = capital / len(to_buy)

                    for ticker in to_buy:
                        price = current_prices[ticker]
                        shares = position_size / price
                        shares_held[ticker] = shares
                        highest_prices[ticker] = price  # Initialize trailing stop
                        capital -= position_size
                        portfolio.append(ticker)
                        total_buys += 1

                        print(f"  BUY  {ticker}: ${price:.2f}")

            # Calculate portfolio value
            portfolio_value = capital
            for ticker, shares in shares_held.items():
                portfolio_value += shares * current_prices[ticker]

            # Create notes
            notes = f'Week {week_num}: '
            if to_sell:
                notes += f'{len(to_sell)} sells ({stop_loss_sells} stops), '
            if slots_to_fill > 0:
                notes += f'{len(to_buy)} buys, '
            notes += f'{len(portfolio)} holdings'

            # Save snapshot
            db.save_portfolio_snapshot(
                take_profit=portfolio[:3] if len(portfolio) >= 3 else portfolio,
                hold=portfolio[3:10] if len(portfolio) > 3 else [],
                buffer=portfolio[10:] if len(portfolio) > 10 else [],
                notes=notes,
                portfolio_value=portfolio_value,
                is_locked=True,
                timestamp=date
            )

            snapshots_created += 1
            print(f"  Portfolio: {len(portfolio)} stocks, Value: ${portfolio_value:,.2f}")

    print(f"\n{'='*70}")
    print(f"TRAILING STOP BACKTEST COMPLETE")
    print(f"{'='*70}")
    print(f"\nCreated {snapshots_created} weekly snapshots")
    print(f"Period: {weekly_dates[0].strftime('%Y-%m-%d')} to {weekly_dates[-1].strftime('%Y-%m-%d')}")

    # Calculate final return
    initial_value = INITIAL_CAPITAL
    final_value = portfolio_value
    total_return = (final_value - initial_value) / initial_value * 100

    print(f"\nTrading Statistics:")
    print(f"  Total Buys:  {total_buys}")
    print(f"  Total Sells: {total_sells}")
    print(f"  Stop Loss Sells: {stop_loss_sells} ({stop_loss_sells/total_sells*100:.1f}% of sells)")

    print(f"\nFinal Portfolio Value: ${final_value:,.2f}")
    print(f"Total Return: {total_return:+.2f}%")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    try:
        # Ask for confirmation
        print("\n" + "="*70)
        print("WARNING: This will clear existing portfolio snapshots")
        print("and populate with trailing stop strategy backtest")
        print("="*70)

        response = input("\nProceed? (yes/no): ")

        if response.lower() == 'yes':
            # Clear existing snapshots
            from database import get_db
            db = get_db()
            conn = db.get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM portfolio_snapshots")
            cursor.execute("DELETE FROM activity_log")
            cursor.execute("DELETE FROM sold_positions")
            conn.commit()
            conn.close()

            print("\nCleared existing data, starting population...\n")

            # Populate from backtest
            populate_database_trailing_stop()

            # Lock all snapshots
            locked = db.lock_all_historical_snapshots()
            print(f"Locked {locked} historical snapshots")
        else:
            print("\nCancelled - no changes made\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
