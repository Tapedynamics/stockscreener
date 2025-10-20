#!/usr/bin/env python3
"""
Backtest Momentum Basket Rotation Strategy
Compares rotation strategy vs buy-and-hold
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import numpy as np

# Configuration
INITIAL_CAPITAL = 150000
PORTFOLIO_SIZE = 12  # Hold 10-12 stocks
TOP_RANK_SELL = 3    # Sell positions ranked #1-#3
REENTRY_WEEKS = 2    # Cooldown period
REENTRY_MIN_RANK = 9 # Must drop to at least rank #9 to re-enter

# Test period
START_DATE = '2025-01-01'
END_DATE = '2025-10-19'

# Universe of tickers (mid-cap growth stocks similar to Finviz criteria)
UNIVERSE = [
    # Current baseline tickers
    'NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
    'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ',
    # Additional mid-cap growth candidates
    'NVDA', 'AMD', 'PLTR', 'COIN', 'MSTR', 'TSLA', 'META',
    'AMZN', 'GOOGL', 'MSFT', 'AAPL', 'NFLX', 'CRM', 'UBER', 'SHOP',
    'SQ', 'PYPL', 'ADBE', 'NOW', 'SNOW', 'DDOG', 'NET', 'CRWD',
    'ZS', 'OKTA', 'PANW', 'FTNT', 'CVNA', 'RIVN', 'LCID'
]

class MomentumBacktest:
    def __init__(self, universe: List[str], start_date: str, end_date: str):
        self.universe = universe
        self.start_date = start_date
        self.end_date = end_date
        self.data = None
        self.weekly_dates = []

    def download_data(self):
        """Download historical price data for all tickers"""
        print(f"\nDownloading data for {len(self.universe)} tickers...")
        print(f"Period: {self.start_date} to {self.end_date}")

        self.data = yf.download(
            self.universe,
            start=self.start_date,
            end=self.end_date,
            progress=False,
            auto_adjust=True
        )

        if self.data.empty:
            raise ValueError("No data downloaded")

        # Get Close prices
        if 'Close' in self.data.columns:
            self.prices = self.data['Close']
        elif isinstance(self.data.columns, pd.MultiIndex):
            self.prices = self.data['Close']
        else:
            self.prices = self.data

        print(f"Downloaded {len(self.prices)} days of data")

        # Generate weekly dates (Mondays)
        date_range = pd.date_range(start=self.start_date, end=self.end_date, freq='W-MON')
        self.weekly_dates = [d for d in date_range if d in self.prices.index or
                            (d + timedelta(days=1)) in self.prices.index or
                            (d + timedelta(days=2)) in self.prices.index]

        print(f"Backtest will run for {len(self.weekly_dates)} weeks")

    def calculate_momentum(self, date, lookback_days=30):
        """Calculate 30-day momentum for all tickers at given date"""
        try:
            # Get price at date
            current_idx = self.prices.index.get_indexer([date], method='nearest')[0]

            # Get price 30 days ago
            lookback_idx = max(0, current_idx - lookback_days)

            current_prices = self.prices.iloc[current_idx]
            past_prices = self.prices.iloc[lookback_idx]

            # Calculate returns
            returns = ((current_prices - past_prices) / past_prices * 100).dropna()

            # Sort by performance (descending)
            ranked = returns.sort_values(ascending=False)

            return ranked

        except Exception as e:
            print(f"Error calculating momentum for {date}: {e}")
            return pd.Series()

    def run_rotation_strategy(self):
        """Run the momentum rotation strategy"""
        portfolio = []  # List of tickers currently held
        sold_stocks = {}  # {ticker: {'date': date, 'rank': rank}}
        trades = []
        portfolio_values = []

        capital = INITIAL_CAPITAL
        shares_held = {}  # {ticker: number of shares}

        print(f"\n{'='*80}")
        print("MOMENTUM ROTATION BACKTEST")
        print(f"{'='*80}\n")

        for week_num, date in enumerate(self.weekly_dates, 1):
            print(f"\n--- Week {week_num}: {date.strftime('%Y-%m-%d')} ---")

            # Calculate momentum rankings
            momentum = self.calculate_momentum(date)

            if len(momentum) == 0:
                print("No momentum data, skipping week")
                continue

            # Get top 15 stocks
            top_15 = momentum.head(15).index.tolist()

            print(f"Top 15 stocks: {', '.join(top_15[:5])}... (showing first 5)")

            if week_num == 1:
                # First week - buy top 12
                portfolio = top_15[:PORTFOLIO_SIZE]
                position_size = capital / len(portfolio)

                # Get current prices
                current_idx = self.prices.index.get_indexer([date], method='nearest')[0]
                current_prices = self.prices.iloc[current_idx]

                for ticker in portfolio:
                    price = current_prices[ticker]
                    shares = position_size / price
                    shares_held[ticker] = shares
                    capital -= position_size  # Reduce capital after buying
                    trades.append({
                        'date': date,
                        'action': 'BUY',
                        'ticker': ticker,
                        'shares': shares,
                        'price': price,
                        'value': position_size
                    })

                print(f"Initial portfolio: {len(portfolio)} stocks")

            else:
                # Get current prices
                current_idx = self.prices.index.get_indexer([date], method='nearest')[0]
                current_prices = self.prices.iloc[current_idx]

                # Create rank dictionary
                ranks = {ticker: i+1 for i, ticker in enumerate(momentum.index)}

                to_sell = []
                to_buy = []

                # Rule 1: Sell top 3 ranked stocks in current portfolio
                portfolio_ranks = [(ticker, ranks.get(ticker, 999)) for ticker in portfolio]
                portfolio_ranks.sort(key=lambda x: x[1])

                for ticker, rank in portfolio_ranks[:TOP_RANK_SELL]:
                    if rank <= 15:  # Only if still in top 15
                        to_sell.append((ticker, 'top_3', rank))
                        sold_stocks[ticker] = {
                            'date': date,
                            'rank': rank,
                            'reason': 'top_3'
                        }

                # Rule 2: Sell stocks that dropped out of top 15
                for ticker in portfolio:
                    if ticker not in top_15:
                        to_sell.append((ticker, 'drop_out', ranks.get(ticker, 999)))
                        if ticker not in [t for t, _, _ in to_sell if _ == 'top_3']:
                            sold_stocks[ticker] = {
                                'date': date,
                                'rank': ranks.get(ticker, 999),
                                'reason': 'drop_out'
                            }

                # Execute sells
                for ticker, reason, rank in to_sell:
                    if ticker in shares_held:
                        shares = shares_held[ticker]
                        price = current_prices[ticker]
                        value = shares * price

                        trades.append({
                            'date': date,
                            'action': 'SELL',
                            'ticker': ticker,
                            'shares': shares,
                            'price': price,
                            'value': value,
                            'reason': reason
                        })

                        capital += value
                        del shares_held[ticker]
                        portfolio.remove(ticker)

                        print(f"  SELL {ticker} (reason: {reason}, rank: {rank})")

                # Determine what to buy
                slots_to_fill = PORTFOLIO_SIZE - len(portfolio)

                # Check re-entry rules
                can_buy = []
                for ticker in top_15:
                    if ticker in portfolio:
                        continue

                    # Check if in cooldown
                    if ticker in sold_stocks:
                        sold_info = sold_stocks[ticker]
                        weeks_since_sold = (date - sold_info['date']).days / 7

                        if sold_info['reason'] == 'top_3':
                            # Must wait 2 weeks AND drop below rank 5
                            current_rank = ranks.get(ticker, 999)
                            if weeks_since_sold >= REENTRY_WEEKS and current_rank >= REENTRY_MIN_RANK:
                                can_buy.append(ticker)
                                del sold_stocks[ticker]  # Clear cooldown
                        else:
                            # Drop-out can re-enter immediately if back in top 15
                            can_buy.append(ticker)
                            del sold_stocks[ticker]
                    else:
                        # Never held before
                        can_buy.append(ticker)

                # Buy lowest-ranked stocks in top 10 (ranks 4-13 range)
                top_10_tickers = [t for t in top_15[:13] if t in can_buy and ranks[t] >= 4]
                to_buy = top_10_tickers[:slots_to_fill]

                # Execute buys
                if to_buy:
                    position_size = capital / len(to_buy)

                    for ticker in to_buy:
                        price = current_prices[ticker]
                        shares = position_size / price
                        shares_held[ticker] = shares
                        capital -= position_size
                        portfolio.append(ticker)

                        trades.append({
                            'date': date,
                            'action': 'BUY',
                            'ticker': ticker,
                            'shares': shares,
                            'price': price,
                            'value': position_size
                        })

                        print(f"  BUY {ticker} (rank: {ranks.get(ticker, 'N/A')})")

            # Calculate portfolio value
            current_idx = self.prices.index.get_indexer([date], method='nearest')[0]
            current_prices = self.prices.iloc[current_idx]

            portfolio_value = capital
            for ticker, shares in shares_held.items():
                portfolio_value += shares * current_prices[ticker]

            portfolio_values.append({
                'date': date,
                'value': portfolio_value,
                'holdings': len(portfolio),
                'cash': capital
            })

            print(f"  Portfolio value: ${portfolio_value:,.2f} ({len(portfolio)} holdings)")

        return portfolio_values, trades

    def run_buy_and_hold(self, tickers: List[str]):
        """Run buy-and-hold strategy for comparison"""
        print(f"\n{'='*80}")
        print("BUY-AND-HOLD BACKTEST (Baseline)")
        print(f"{'='*80}\n")

        capital = INITIAL_CAPITAL
        position_size = capital / len(tickers)
        shares_held = {}

        # Buy at start
        start_idx = 0
        start_prices = self.prices.iloc[start_idx]

        for ticker in tickers:
            if ticker in start_prices:
                price = start_prices[ticker]
                shares = position_size / price
                shares_held[ticker] = shares

        print(f"Bought {len(shares_held)} stocks at start")

        # Track value weekly
        values = []
        for date in self.weekly_dates:
            current_idx = self.prices.index.get_indexer([date], method='nearest')[0]
            current_prices = self.prices.iloc[current_idx]

            total_value = 0
            for ticker, shares in shares_held.items():
                if ticker in current_prices:
                    total_value += shares * current_prices[ticker]

            values.append({
                'date': date,
                'value': total_value
            })

        return values

def main():
    # Initialize backtest
    bt = MomentumBacktest(UNIVERSE, START_DATE, END_DATE)

    # Download data
    bt.download_data()

    # Run rotation strategy
    rotation_values, trades = bt.run_rotation_strategy()

    # Run buy-and-hold with baseline tickers
    baseline_tickers = ['NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
                       'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ']
    buyhold_values = bt.run_buy_and_hold(baseline_tickers)

    # Compare results
    print(f"\n{'='*80}")
    print("RESULTS COMPARISON")
    print(f"{'='*80}\n")

    rotation_final = rotation_values[-1]['value']
    rotation_return = (rotation_final - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    buyhold_final = buyhold_values[-1]['value']
    buyhold_return = (buyhold_final - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    print(f"Momentum Rotation Strategy:")
    print(f"  Final Value:  ${rotation_final:,.2f}")
    print(f"  Total Return: {rotation_return:+.2f}%")
    print(f"  Total Trades: {len(trades)}")

    print(f"\nBuy-and-Hold (15 Baseline Stocks):")
    print(f"  Final Value:  ${buyhold_final:,.2f}")
    print(f"  Total Return: {buyhold_return:+.2f}%")

    print(f"\nDifference:")
    diff_value = rotation_final - buyhold_final
    diff_return = rotation_return - buyhold_return
    print(f"  Value:  ${diff_value:+,.2f}")
    print(f"  Return: {diff_return:+.2f}%")

    if rotation_return > buyhold_return:
        print(f"\n[WIN] Rotation strategy OUTPERFORMED by {diff_return:.2f}%")
    else:
        print(f"\n[LOSS] Rotation strategy UNDERPERFORMED by {abs(diff_return):.2f}%")

    print(f"\n{'='*80}\n")

    # Trade statistics
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    sell_trades = [t for t in trades if t['action'] == 'SELL']

    print("Trade Statistics:")
    print(f"  Total Buys:  {len(buy_trades)}")
    print(f"  Total Sells: {len(sell_trades)}")

    if sell_trades:
        top3_sells = len([t for t in sell_trades if t.get('reason') == 'top_3'])
        dropout_sells = len([t for t in sell_trades if t.get('reason') == 'drop_out'])
        print(f"  Sells (Top 3):    {top3_sells}")
        print(f"  Sells (Drop out): {dropout_sells}")

    print()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
