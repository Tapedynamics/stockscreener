#!/usr/bin/env python3
"""
Price tracking module using Yahoo Finance
"""

import yfinance as yf
from datetime import datetime, timedelta
from database import get_db
import logging

logger = logging.getLogger(__name__)


class PriceTracker:
    """Track stock prices and performance"""

    def __init__(self):
        self.db = get_db()

    def get_current_price(self, ticker):
        """
        Get current price for a ticker

        Args:
            ticker: Stock ticker symbol

        Returns:
            float: Current price or None if error
        """
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1d')

            if not data.empty:
                return float(data['Close'].iloc[-1])

            return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None

    def get_prices_batch(self, tickers):
        """
        Get current prices for multiple tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            dict: {ticker: price}
        """
        prices = {}

        try:
            # Download data for all tickers at once (more efficient)
            data = yf.download(tickers, period='1d', progress=False, show_errors=False)

            if 'Close' in data.columns:
                for ticker in tickers:
                    try:
                        if len(tickers) == 1:
                            price = float(data['Close'].iloc[-1])
                        else:
                            price = float(data['Close'][ticker].iloc[-1])
                        prices[ticker] = price
                    except Exception as e:
                        logger.warning(f"Could not get price for {ticker}: {e}")
                        prices[ticker] = None

        except Exception as e:
            logger.error(f"Error in batch price fetch: {e}")
            # Fallback to individual fetch
            for ticker in tickers:
                prices[ticker] = self.get_current_price(ticker)

        return prices

    def save_price(self, ticker, price):
        """
        Save stock price to database

        Args:
            ticker: Stock ticker symbol
            price: Current price
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        today = datetime.now().date()

        cursor.execute('''
            INSERT OR REPLACE INTO stock_performance
            (ticker, date, price, performance)
            VALUES (?, ?, ?, NULL)
        ''', (ticker, today, price))

        conn.commit()
        conn.close()

    def calculate_performance(self, ticker, days=7):
        """
        Calculate performance over last N days

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back

        Returns:
            float: Performance percentage or None
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        cursor.execute('''
            SELECT price, date FROM stock_performance
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        ''', (ticker, start_date, end_date))

        rows = cursor.fetchall()
        conn.close()

        if len(rows) >= 2:
            start_price = rows[0]['price']
            end_price = rows[-1]['price']

            if start_price and end_price and start_price > 0:
                performance = ((end_price - start_price) / start_price) * 100
                return round(performance, 2)

        return None

    def update_portfolio_prices(self, portfolio):
        """
        Update prices for all stocks in portfolio

        Args:
            portfolio: Portfolio dict with take_profit, hold, buffer lists

        Returns:
            dict: {ticker: {'price': float, 'performance': float}}
        """
        all_tickers = (
            portfolio.get('take_profit', []) +
            portfolio.get('hold', []) +
            portfolio.get('buffer', [])
        )

        if not all_tickers:
            return {}

        # Get current prices
        prices = self.get_prices_batch(all_tickers)

        # Save to database and calculate performance
        results = {}

        for ticker in all_tickers:
            price = prices.get(ticker)

            if price:
                # Save price
                self.save_price(ticker, price)

                # Calculate performance (7 days)
                perf = self.calculate_performance(ticker, days=7)

                results[ticker] = {
                    'price': price,
                    'performance': perf if perf is not None else 0.0
                }
            else:
                results[ticker] = {
                    'price': None,
                    'performance': 0.0
                }

        return results

    def get_portfolio_stats(self, portfolio, initial_value=150000):
        """
        Calculate portfolio statistics

        Args:
            portfolio: Portfolio dict
            initial_value: Initial portfolio value (default $150k)

        Returns:
            dict: Portfolio statistics
        """
        stock_data = self.update_portfolio_prices(portfolio)

        total_positions = len(stock_data)

        if total_positions == 0:
            return {
                'total_value': initial_value,
                'total_positions': 0,
                'weekly_performance': 0.0,
                'weekly_gain': 0.0,
                'avg_performance': 0.0
            }

        # Calculate average performance
        performances = [data['performance'] for data in stock_data.values() if data['performance'] is not None]

        if performances:
            avg_perf = sum(performances) / len(performances)
        else:
            avg_perf = 0.0

        # Calculate portfolio value based on performance
        weekly_gain = initial_value * (avg_perf / 100)
        total_value = initial_value + weekly_gain

        return {
            'total_value': round(total_value, 2),
            'total_positions': total_positions,
            'weekly_performance': round(avg_perf, 2),
            'weekly_gain': round(weekly_gain, 2),
            'avg_performance': round(avg_perf, 2),
            'stock_data': stock_data
        }


def get_price_tracker():
    """Get PriceTracker instance"""
    return PriceTracker()
