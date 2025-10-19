#!/usr/bin/env python3
"""
Portfolio simulator - Simulates portfolio performance from Jan 1, 2025
"""

import yfinance as yf
from datetime import datetime, timedelta
from database import get_db
import logging

logger = logging.getLogger(__name__)


class PortfolioSimulator:
    """Simulate portfolio performance over time"""

    def __init__(self, initial_value=150000):
        self.db = get_db()
        self.initial_value = initial_value

    def simulate_portfolio_history(self, portfolio, start_date=None, end_date=None):
        """
        Simulate portfolio performance from start date to end date

        Args:
            portfolio: Dict with take_profit, hold, buffer lists
            start_date: Start date (default: 2025-01-01)
            end_date: End date (default: today)

        Returns:
            dict: Historical performance data
        """
        # Default dates
        if start_date is None:
            start_date = datetime(2025, 1, 1)
        if end_date is None:
            end_date = datetime.now()

        # Get all tickers
        all_tickers = (
            portfolio.get('take_profit', []) +
            portfolio.get('hold', []) +
            portfolio.get('buffer', [])
        )

        if not all_tickers:
            return {
                'dates': [],
                'values': [],
                'performances': []
            }

        try:
            # Download historical data for all tickers
            data = yf.download(
                all_tickers,
                start=start_date,
                end=end_date,
                progress=False,
                show_errors=False
            )

            if data.empty:
                logger.warning("No historical data available")
                return {
                    'dates': [],
                    'values': [],
                    'performances': []
                }

            # Get close prices
            if len(all_tickers) == 1:
                close_prices = data['Close'].to_frame()
                close_prices.columns = [all_tickers[0]]
            else:
                close_prices = data['Close']

            # Calculate portfolio value per day
            dates = []
            values = []
            performances = []

            position_value = self.initial_value / len(all_tickers)  # Equal weight

            for date_idx in close_prices.index:
                date_val = date_idx.date()
                daily_prices = close_prices.loc[date_idx]

                # Calculate total portfolio value for this day
                total_value = 0
                valid_stocks = 0

                for ticker in all_tickers:
                    try:
                        if len(all_tickers) == 1:
                            price = float(daily_prices)
                        else:
                            price = float(daily_prices[ticker])

                        if price > 0:
                            # Get initial price (first day)
                            if len(all_tickers) == 1:
                                initial_price = float(close_prices.iloc[0])
                            else:
                                initial_price = float(close_prices[ticker].iloc[0])

                            if initial_price > 0:
                                # Calculate position value based on performance
                                stock_performance = (price / initial_price)
                                current_position_value = position_value * stock_performance
                                total_value += current_position_value
                                valid_stocks += 1
                    except:
                        continue

                if valid_stocks > 0:
                    # Add missing positions at initial value (not in data)
                    missing_positions = len(all_tickers) - valid_stocks
                    total_value += missing_positions * position_value

                    # Calculate overall performance
                    performance = ((total_value - self.initial_value) / self.initial_value) * 100

                    dates.append(date_val.isoformat())
                    values.append(round(total_value, 2))
                    performances.append(round(performance, 2))

            return {
                'dates': dates,
                'values': values,
                'performances': performances,
                'initial_value': self.initial_value,
                'current_value': values[-1] if values else self.initial_value,
                'total_return': performances[-1] if performances else 0.0
            }

        except Exception as e:
            logger.error(f"Error simulating portfolio history: {e}")
            return {
                'dates': [],
                'values': [],
                'performances': [],
                'error': str(e)
            }

    def get_timeframe_data(self, portfolio, timeframe='YTD'):
        """
        Get portfolio data for specific timeframe

        Args:
            portfolio: Portfolio dict
            timeframe: '1M', '3M', '6M', 'YTD', 'ALL'

        Returns:
            dict: Performance data for timeframe
        """
        end_date = datetime.now()

        if timeframe == '1M':
            start_date = end_date - timedelta(days=30)
        elif timeframe == '3M':
            start_date = end_date - timedelta(days=90)
        elif timeframe == '6M':
            start_date = end_date - timedelta(days=180)
        elif timeframe == 'YTD':
            start_date = datetime(2025, 1, 1)
        elif timeframe == 'ALL':
            start_date = datetime(2025, 1, 1)
        else:
            start_date = datetime(2025, 1, 1)

        return self.simulate_portfolio_history(portfolio, start_date, end_date)


def get_simulator(initial_value=150000):
    """Get PortfolioSimulator instance"""
    return PortfolioSimulator(initial_value)
