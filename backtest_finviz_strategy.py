#!/usr/bin/env python3
"""
Backtest Finviz Strategy with Yahoo Finance historical data
Uses current Finviz universe (20 stocks that pass all filters)
Calculates historical 4-week momentum rankings
Applies 15% trailing stop
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List
from database import get_db
from stock_screener import get_finviz_stocks
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
INITIAL_CAPITAL = 150000
PORTFOLIO_SIZE = 12
TRAILING_STOP_PERCENT = 0.15  # 15%

START_DATE = '2025-01-01'
END_DATE = '2025-10-19'

# Get Finviz URL
FINVIZ_URL = os.getenv(
    'FINVIZ_URL',
    "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"
)

def calculate_momentum(prices, date, lookback_days=30):
    """Calculate 4-week momentum at given date"""
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

def run_backtest():
    """Run backtest with Finviz universe and Yahoo historical data"""

    db = get_db()

    print("\n" + "="*70)
    print("FINVIZ STRATEGY BACKTEST WITH YAHOO HISTORICAL DATA")
    print("="*70)
    print(f"Portfolio size: {PORTFOLIO_SIZE} stocks")
    print(f"Trailing stop: {TRAILING_STOP_PERCENT*100:.0f}%")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.0f}")

    # Get current Finviz universe
    print(f"\nFetching current Finviz universe...")
    try:
        universe = get_finviz_stocks(FINVIZ_URL)
        print(f"Finviz returned {len(universe)} stocks that pass all filters")
        print(f"Using these stocks as universe: {', '.join(universe[:10])}...")
    except Exception as e:
        print(f"Error fetching Finviz: {e}")
        return

    # Download historical data from Yahoo
    print(f"\nDownloading historical data from Yahoo Finance...")
    data = yf.download(universe, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)

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
    shares_held = {}
    highest_prices = {}

    snapshots_created = 0
    total_sells = 0
    total_buys = 0
    stop_loss_sells = 0

    for week_num, date in enumerate(weekly_dates, 1):
        print(f"Week {week_num}/{len(weekly_dates)}: {date.strftime('%Y-%m-%d')}")

        # Calculate 4-week momentum (same as Finviz sorting)
        momentum = calculate_momentum(prices, date, lookback_days=30)

        if len(momentum) == 0:
            print("  No momentum data, skipping")
            continue

        # Top 15 by momentum (mimics Finviz sorting)
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
                highest_prices[ticker] = price
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
            print(f"  Initial: {len(portfolio)} stocks, Value: ${portfolio_value:,.2f}")

        else:
            to_sell = []

            # Check trailing stops and top 15 membership
            for ticker in list(portfolio):
                current_price = current_prices[ticker]

                # Update highest price
                if current_price > highest_prices[ticker]:
                    highest_prices[ticker] = current_price

                # Calculate stop price
                stop_price = highest_prices[ticker] * (1 - TRAILING_STOP_PERCENT)

                # Sell if hit stop or out of top 15
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

                    db.record_sale(ticker, reason, 0)

                    if reason == 'trailing_stop':
                        print(f"  SELL {ticker}: ${price:.2f} < ${stop_price:.2f} (stop)")
                    else:
                        print(f"  SELL {ticker}: out of top 15")

            # Buy to fill portfolio
            slots_to_fill = PORTFOLIO_SIZE - len(portfolio)

            if slots_to_fill > 0:
                candidates = [t for t in top_15 if t not in portfolio]
                to_buy = candidates[:slots_to_fill]

                if to_buy:
                    position_size = capital / len(to_buy)

                    for ticker in to_buy:
                        price = current_prices[ticker]
                        shares = position_size / price
                        shares_held[ticker] = shares
                        highest_prices[ticker] = price
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
                notes += f'{len(to_sell)} sells, '
            if slots_to_fill > 0 and to_buy:
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
    print(f"BACKTEST COMPLETE")
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
    print(f"Average Weekly Return: {total_return/(len(weekly_dates)-1):+.2f}%")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    try:
        print("\n" + "="*70)
        print("WARNING: This will clear existing portfolio snapshots")
        print("and populate with Finviz strategy backtest")
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

            print("\nCleared existing data, starting backtest...\n")

            # Run backtest
            run_backtest()

            # Lock all snapshots
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE portfolio_snapshots SET is_locked = 1')
            conn.commit()
            count = cursor.rowcount
            conn.close()
            print(f"Locked {count} historical snapshots")
        else:
            print("\nCancelled - no changes made\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
