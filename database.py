#!/usr/bin/env python3
"""
Database models and initialization for Stock Screener
"""

import sqlite3
from datetime import datetime
import json
import os


class Database:
    def __init__(self, db_path='portfolio.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Get database connection"""
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
                notes TEXT
            )
        ''')

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

        conn.commit()
        conn.close()

    def save_portfolio_snapshot(self, take_profit, hold, buffer, notes=None):
        """Save a portfolio snapshot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO portfolio_snapshots
            (take_profit, hold, buffer, total_stocks, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            json.dumps(take_profit),
            json.dumps(hold),
            json.dumps(buffer),
            len(take_profit) + len(hold) + len(buffer),
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

    def set_setting(self, key, value):
        """Set a setting value"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))

        conn.commit()
        conn.close()


# Convenience function
def get_db():
    """Get database instance"""
    return Database()
