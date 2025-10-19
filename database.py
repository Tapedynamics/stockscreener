#!/usr/bin/env python3
"""
Database models and initialization for Stock Screener
"""

import sqlite3
from datetime import datetime
import json
import os
import logging
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = 'portfolio.db'):
        """Initialize database connection

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection

        Returns:
            SQLite connection with Row factory
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Portfolio snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                take_profit TEXT NOT NULL,
                hold TEXT NOT NULL,
                buffer TEXT NOT NULL,
                total_stocks INTEGER,
                portfolio_value REAL,
                notes TEXT
            )
        ''')

        # Add portfolio_value column if it doesn't exist (migration)
        try:
            cursor.execute('ALTER TABLE portfolio_snapshots ADD COLUMN portfolio_value REAL')
            logger.info("Added portfolio_value column to portfolio_snapshots")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Activity log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                action_type TEXT NOT NULL,
                ticker TEXT,
                description TEXT NOT NULL,
                metadata TEXT
            )
        ''')

        # Stock performance tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                price REAL,
                performance REAL,
                UNIQUE(ticker, date)
            )
        ''')

        # Portfolio settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_portfolio_timestamp
            ON portfolio_snapshots(timestamp DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_activity_timestamp
            ON activity_log(timestamp DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_stock_ticker_date
            ON stock_performance(ticker, date DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_activity_action_type
            ON activity_log(action_type, timestamp DESC)
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def save_portfolio_snapshot(self, take_profit, hold, buffer, notes=None, portfolio_value=None):
        """Save a portfolio snapshot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO portfolio_snapshots
            (take_profit, hold, buffer, total_stocks, portfolio_value, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            json.dumps(take_profit),
            json.dumps(hold),
            json.dumps(buffer),
            len(take_profit) + len(hold) + len(buffer),
            portfolio_value,
            notes
        ))

        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return snapshot_id

    def get_latest_portfolio(self):
        """Get the most recent portfolio snapshot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM portfolio_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        ''')

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row['id'],
                'timestamp': row['timestamp'],
                'take_profit': json.loads(row['take_profit']),
                'hold': json.loads(row['hold']),
                'buffer': json.loads(row['buffer']),
                'total_stocks': row['total_stocks'],
                'notes': row['notes']
            }
        return None

    def get_portfolio_history(self, limit=10):
        """Get portfolio history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM portfolio_snapshots
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'take_profit': json.loads(row['take_profit']),
                'hold': json.loads(row['hold']),
                'buffer': json.loads(row['buffer']),
                'total_stocks': row['total_stocks'],
                'notes': row['notes']
            })

        return history

    def add_activity_log(self, action_type, description, ticker=None, metadata=None):
        """Add an activity log entry"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO activity_log
            (action_type, ticker, description, metadata)
            VALUES (?, ?, ?, ?)
        ''', (
            action_type,
            ticker,
            description,
            json.dumps(metadata) if metadata else None
        ))

        log_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return log_id

    def get_activity_log(self, limit=20):
        """Get recent activity log entries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM activity_log
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            logs.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'action_type': row['action_type'],
                'ticker': row['ticker'],
                'description': row['description'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else None
            })

        return logs

    def compare_portfolios(self, new_portfolio, old_portfolio):
        """Compare two portfolios and generate change log"""
        if not old_portfolio:
            return {
                'added': new_portfolio['take_profit'] + new_portfolio['hold'] + new_portfolio['buffer'],
                'removed': [],
                'moved': []
            }

        # Flatten portfolios
        old_stocks = set(old_portfolio['take_profit'] + old_portfolio['hold'] + old_portfolio['buffer'])
        new_stocks = set(new_portfolio['take_profit'] + new_portfolio['hold'] + new_portfolio['buffer'])

        added = list(new_stocks - old_stocks)
        removed = list(old_stocks - new_stocks)

        # Detect position changes
        moved = []
        for ticker in (old_stocks & new_stocks):
            old_pos = self._get_position_category(ticker, old_portfolio)
            new_pos = self._get_position_category(ticker, new_portfolio)
            if old_pos != new_pos:
                moved.append({
                    'ticker': ticker,
                    'from': old_pos,
                    'to': new_pos
                })

        return {
            'added': added,
            'removed': removed,
            'moved': moved
        }

    def _get_position_category(self, ticker, portfolio):
        """Get the category of a ticker in a portfolio"""
        if ticker in portfolio['take_profit']:
            return 'take_profit'
        elif ticker in portfolio['hold']:
            return 'hold'
        elif ticker in portfolio['buffer']:
            return 'buffer'
        return None

    def get_setting(self, key, default=None):
        """Get a setting value"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return row['value']
        return default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value

        Args:
            key: Setting key
            value: Setting value
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))

        conn.commit()
        conn.close()

    def batch_save_prices(self, price_data: List[Tuple[str, str, float]]) -> None:
        """Batch save multiple stock prices

        Args:
            price_data: List of tuples (ticker, date, price)
        """
        if not price_data:
            return

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.executemany('''
                INSERT OR REPLACE INTO stock_performance
                (ticker, date, price, performance)
                VALUES (?, ?, ?, NULL)
            ''', price_data)

            conn.commit()
            logger.info(f"Batch saved {len(price_data)} price records")
        except Exception as e:
            logger.error(f"Error in batch save: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_recent_prices(self, ticker: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent prices for a ticker

        Args:
            ticker: Stock ticker symbol
            days: Number of days to retrieve

        Returns:
            List of price records
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ticker, date, price, performance
            FROM stock_performance
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        ''', (ticker, days))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


# Convenience function
def get_db() -> Database:
    """Get database instance

    Returns:
        Database instance
    """
    return Database()
