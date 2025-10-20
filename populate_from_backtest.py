#!/usr/bin/env python3
"""
Populate database with historical snapshots from momentum rotation backtest
Creates 41 weeks of real trading history based on the backtest results
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from database import get_db

# Configuration (same as backtest)
INITIAL_CAPITAL = 150000
PORTFOLIO_SIZE = 12
TOP_RANK_SELL = 3
REENTRY_WEEKS = 2
REENTRY_MIN_RANK = 9

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

def populate_database_from_backtest():
    """Run backtest and populate database with snapshots"""

    db = get_db()

    print("\n" + "="*70)
    print("POPULATING DATABASE FROM MOMENTUM ROTATION BACKTEST")
    print("="*70)

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

    # Backtest state
    portfolio = []
    sold_stocks = {}
    capital = INITIAL_CAPITAL
    shares_held = {}

    snapshots_created = 0

    for week_num, date in enumerate(weekly_dates, 1):
        print(f"Week {week_num}/{len(weekly_dates)}: {date.strftime('%Y-%m-%d')}")

        # Calculate momentum
        momentum = calculate_momentum(prices, date)

        if len(momentum) == 0:
            print("  No momentum data, skipping")
            continue

        top_15 = momentum.head(15).index.tolist()

        if week_num == 1:
            # First week - buy top 12
            portfolio = top_15[:PORTFOLIO_SIZE]
            position_size = capital / len(portfolio)

            current_idx = prices.index.get_indexer([date], method='nearest')[0]
            current_prices = prices.iloc[current_idx]

            for ticker in portfolio:
                price = current_prices[ticker]
                shares = position_size / price
                shares_held[ticker] = shares

            # Calculate portfolio value
            portfolio_value = sum(shares_held[t] * current_prices[t] for t in portfolio)

            # Save snapshot (locked as historical backtest data)
            db.save_portfolio_snapshot(
                take_profit=portfolio[:3],
                hold=portfolio[3:10] if len(portfolio) > 3 else [],
                buffer=portfolio[10:] if len(portfolio) > 10 else [],
                notes=f'Week {week_num}: Initial portfolio ({len(portfolio)} stocks)',
                portfolio_value=portfolio_value,
                is_locked=True,
                timestamp=date  # Use actual week date (Monday)
            )

            snapshots_created += 1
            print(f"  Created initial snapshot - Value: ${portfolio_value:,.2f}")

        else:
            # Calculate current value before trades
            current_idx = prices.index.get_indexer([date], method='nearest')[0]
            current_prices = prices.iloc[current_idx]

            ranks = {ticker: i+1 for i, ticker in enumerate(momentum.index)}

            to_sell = []

            # Sell top 3
            portfolio_ranks = [(ticker, ranks.get(ticker, 999)) for ticker in portfolio]
            portfolio_ranks.sort(key=lambda x: x[1])

            for ticker, rank in portfolio_ranks[:TOP_RANK_SELL]:
                if rank <= 15:
                    to_sell.append((ticker, 'top_3', rank))
                    sold_stocks[ticker] = {
                        'date': date,
                        'rank': rank,
                        'reason': 'top_3'
                    }

            # Sell drop-outs
            for ticker in portfolio:
                if ticker not in top_15:
                    rank = ranks.get(ticker, 999)
                    if ticker not in [t for t, _, _ in to_sell]:
                        to_sell.append((ticker, 'drop_out', rank))
                        sold_stocks[ticker] = {
                            'date': date,
                            'rank': rank,
                            'reason': 'drop_out'
                        }

            # Execute sells
            for ticker, reason, rank in to_sell:
                if ticker in shares_held:
                    shares = shares_held[ticker]
                    price = current_prices[ticker]
                    value = shares * price
                    capital += value
                    del shares_held[ticker]
                    portfolio.remove(ticker)

                    # Record sale in database
                    db.record_sale(ticker, reason, rank)

            # Determine buys
            slots_to_fill = PORTFOLIO_SIZE - len(portfolio)
            can_buy = []

            for ticker in top_15:
                if ticker in portfolio:
                    continue

                if ticker in sold_stocks:
                    sold_info = sold_stocks[ticker]
                    weeks_since_sold = (date - sold_info['date']).days / 7
                    current_rank = ranks.get(ticker, 999)

                    if sold_info['reason'] == 'top_3':
                        if weeks_since_sold >= REENTRY_WEEKS and current_rank >= REENTRY_MIN_RANK:
                            can_buy.append(ticker)
                            del sold_stocks[ticker]
                    else:
                        can_buy.append(ticker)
                        del sold_stocks[ticker]
                else:
                    can_buy.append(ticker)

            # Buy lowest-ranked in top 10
            top_10_tickers = [t for t in top_15[:13] if t in can_buy and ranks[t] >= 4]
            to_buy = top_10_tickers[:slots_to_fill]

            # Execute buys
            if to_buy and len(portfolio) + len(to_buy) > 0:
                position_size = capital / (len(portfolio) + len(to_buy))

                for ticker in to_buy:
                    price = current_prices[ticker]
                    shares = position_size / price
                    shares_held[ticker] = shares
                    capital -= position_size
                    portfolio.append(ticker)

                    # Mark as rebought if was in cooldown
                    db.mark_rebought(ticker)

            # Calculate portfolio value
            portfolio_value = capital
            for ticker, shares in shares_held.items():
                portfolio_value += shares * current_prices[ticker]

            # Create notes
            notes = f'Week {week_num}: '
            if to_sell:
                notes += f'{len(to_sell)} sells, '
            if to_buy:
                notes += f'{len(to_buy)} buys, '
            notes += f'{len(portfolio)} holdings'

            # Save snapshot (locked as historical backtest data)
            db.save_portfolio_snapshot(
                take_profit=portfolio[:3] if len(portfolio) >= 3 else portfolio,
                hold=portfolio[3:10] if len(portfolio) > 3 else [],
                buffer=portfolio[10:] if len(portfolio) > 10 else [],
                notes=notes,
                portfolio_value=portfolio_value,
                is_locked=True,
                timestamp=date  # Use actual week date (Monday)
            )

            snapshots_created += 1
            print(f"  Snapshot saved - Value: ${portfolio_value:,.2f} ({len(portfolio)} stocks)")

    print(f"\n{'='*70}")
    print(f"DATABASE POPULATED SUCCESSFULLY")
    print(f"{'='*70}")
    print(f"\nCreated {snapshots_created} weekly snapshots")
    print(f"Period: {weekly_dates[0].strftime('%Y-%m-%d')} to {weekly_dates[-1].strftime('%Y-%m-%d')}")

    # Calculate final return
    initial_value = INITIAL_CAPITAL
    final_value = portfolio_value
    total_return = (final_value - initial_value) / initial_value * 100

    print(f"\nFinal Portfolio Value: ${final_value:,.2f}")
    print(f"Total Return: {total_return:+.2f}%")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    try:
        # Ask for confirmation
        print("\n" + "="*70)
        print("WARNING: This will clear existing portfolio snapshots")
        print("and populate with momentum rotation backtest history")
        print("="*70)

        response = input("\nProceed? (yes/no): ")

        if response.lower() == 'yes':
            # Clear existing snapshots (except baseline)
            from database import get_db
            db = get_db()
            conn = db.get_connection()
            cursor = conn.cursor()

            # Keep only baseline snapshots
            cursor.execute("DELETE FROM portfolio_snapshots WHERE notes NOT LIKE '%BASELINE%'")
            cursor.execute("DELETE FROM activity_log")
            cursor.execute("DELETE FROM sold_positions")
            conn.commit()
            conn.close()

            print("\nCleared existing data, starting population...\n")

            # Populate from backtest
            populate_database_from_backtest()
        else:
            print("\nCancelled - no changes made\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
