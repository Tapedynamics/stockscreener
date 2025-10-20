#!/usr/bin/env python3
"""
Database models and initialization for Stock Screener
"""

from db_adapter import adapter
from datetime import datetime
import json
import os
import logging
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = 'portfolio.db', skip_init: bool = False):
        """Initialize database connection

        Args:
            db_path: Path to SQLite database file
            skip_init: If True, skip init_db() call (useful for PostgreSQL migration)
        """
        self.db_path = db_path
        if not skip_init:
            try:
                self.init_db()
            except Exception as e:
                logger.error(f"Failed to initialize database (migration might be needed): {e}")
                # Don't raise - allow app to start even if init fails
                # Migration endpoint will fix the schema

    def get_connection(self):
        """Get database connection

        Returns:
            Database connection with Row factory
        """
        return adapter.get_connection(self.db_path)

    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Portfolio snapshots table
        adapter.execute(cursor, '''
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
            adapter.execute(cursor, 'ALTER TABLE portfolio_snapshots ADD COLUMN portfolio_value REAL')
            logger.info("Added portfolio_value column to portfolio_snapshots")
        except Exception:
            pass  # Column already exists

        # Add is_locked column if it doesn't exist (migration)
        try:
            adapter.execute(cursor, 'ALTER TABLE portfolio_snapshots ADD COLUMN is_locked BOOLEAN DEFAULT 0')
            logger.info("Added is_locked column to portfolio_snapshots")
        except Exception:
            pass  # Column already exists

        # Activity log table
        adapter.execute(cursor, '''
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
        adapter.execute(cursor, '''
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
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Sold positions tracking (for momentum rotation strategy)
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS sold_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                sold_date DATETIME NOT NULL,
                sold_reason TEXT NOT NULL,
                sold_rank INTEGER,
                can_rebuy_after DATETIME,
                rebought BOOLEAN DEFAULT 0,
                rebought_date DATETIME
            )
        ''')

        # Trade execution tracking (detailed order tickets)
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                ticker TEXT NOT NULL,
                company_name TEXT,
                action TEXT NOT NULL,
                rank INTEGER,
                price REAL NOT NULL,
                shares REAL NOT NULL,
                capital_allocated REAL NOT NULL,
                total_cost REAL NOT NULL,
                cash_remaining REAL,
                status TEXT DEFAULT 'FILLED',
                strategy_note TEXT,
                metadata TEXT
            )
        ''')

        # Create indexes for performance
        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_portfolio_timestamp
            ON portfolio_snapshots(timestamp DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_activity_timestamp
            ON activity_log(timestamp DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_stock_ticker_date
            ON stock_performance(ticker, date DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_activity_action_type
            ON activity_log(action_type, timestamp DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_sold_ticker_date
            ON sold_positions(ticker, sold_date DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp
            ON trades(timestamp DESC)
        ''')

        adapter.execute(cursor, '''
            CREATE INDEX IF NOT EXISTS idx_trades_ticker
            ON trades(ticker, timestamp DESC)
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def save_portfolio_snapshot(self, take_profit, hold, buffer, notes=None, portfolio_value=None, is_locked=False, timestamp=None):
        """Save a portfolio snapshot

        Args:
            take_profit: List of tickers in take profit zone
            hold: List of tickers to hold
            buffer: List of tickers in buffer zone
            notes: Optional notes
            portfolio_value: Portfolio value in dollars
            is_locked: If True, snapshot cannot be modified/deleted (for historical data)
            timestamp: Optional timestamp (datetime object or ISO string). If None, uses current time
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if timestamp:
            # Custom timestamp provided (for historical data)
            if hasattr(timestamp, 'isoformat'):
                # It's a datetime object
                timestamp_str = timestamp.isoformat()
            else:
                # It's already a string
                timestamp_str = timestamp

            adapter.execute(cursor, '''
                INSERT INTO portfolio_snapshots
                (timestamp, take_profit, hold, buffer, total_stocks, portfolio_value, notes, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp_str,
                json.dumps(take_profit),
                json.dumps(hold),
                json.dumps(buffer),
                len(take_profit) + len(hold) + len(buffer),
                portfolio_value,
                notes,
                1 if is_locked else 0
            ))
        else:
            # Use default CURRENT_TIMESTAMP
            adapter.execute(cursor, '''
                INSERT INTO portfolio_snapshots
                (take_profit, hold, buffer, total_stocks, portfolio_value, notes, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                json.dumps(take_profit),
                json.dumps(hold),
                json.dumps(buffer),
                len(take_profit) + len(hold) + len(buffer),
                portfolio_value,
                notes,
                1 if is_locked else 0
            ))

        snapshot_id = adapter.get_last_insert_id(cursor)
        conn.commit()
        conn.close()

        return snapshot_id

    def get_latest_portfolio(self):
        """Get the most recent portfolio snapshot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        adapter.execute(cursor, '''
            SELECT * FROM portfolio_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        ''')

        row = adapter.fetchone_dict(cursor)
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

        adapter.execute(cursor, '''
            SELECT * FROM portfolio_snapshots
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = adapter.fetchall_dict(cursor)
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
                'portfolio_value': row['portfolio_value'],
                'notes': row['notes']
            })

        return history

    def add_activity_log(self, action_type, description, ticker=None, metadata=None):
        """Add an activity log entry"""
        conn = self.get_connection()
        cursor = conn.cursor()

        adapter.execute(cursor, '''
            INSERT INTO activity_log
            (action_type, ticker, description, metadata)
            VALUES (?, ?, ?, ?)
        ''', (
            action_type,
            ticker,
            description,
            json.dumps(metadata) if metadata else None
        ))

        log_id = adapter.get_last_insert_id(cursor)
        conn.commit()
        conn.close()

        return log_id

    def get_activity_log(self, limit=20):
        """Get recent activity log entries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        adapter.execute(cursor, '''
            SELECT * FROM activity_log
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = adapter.fetchall_dict(cursor)
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

        adapter.execute(cursor, 'SELECT value FROM settings WHERE key = ?', (key,))
        row = adapter.fetchone_dict(cursor)
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

        adapter.execute(cursor, '''
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
            cursor.executemany(
                adapter.convert_query('''
                    INSERT OR REPLACE INTO stock_performance
                    (ticker, date, price, performance)
                    VALUES (?, ?, ?, NULL)
                '''),
                price_data
            )

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

        adapter.execute(cursor, '''
            SELECT ticker, date, price, performance
            FROM stock_performance
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        ''', (ticker, days))

        rows = adapter.fetchall_dict(cursor)
        conn.close()

        return rows

    def record_sale(self, ticker: str, reason: str, rank: int = None) -> int:
        """Record a stock sale for momentum rotation tracking

        Args:
            ticker: Stock ticker sold
            reason: Reason for sale ('top_3' or 'drop_out')
            rank: Rank at time of sale

        Returns:
            ID of created record
        """
        from datetime import datetime, timedelta

        conn = self.get_connection()
        cursor = conn.cursor()

        sold_date = datetime.now()

        # Calculate can_rebuy_after based on reason
        if reason == 'top_3':
            # Must wait 2 weeks for top 3 sales
            can_rebuy_after = sold_date + timedelta(weeks=2)
        else:
            # Drop-outs can rebuy immediately if back in top 15
            can_rebuy_after = sold_date

        adapter.execute(cursor, '''
            INSERT INTO sold_positions
            (ticker, sold_date, sold_reason, sold_rank, can_rebuy_after)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticker, sold_date.isoformat(), reason, rank, can_rebuy_after.isoformat()))

        record_id = adapter.get_last_insert_id(cursor)
        conn.commit()
        conn.close()

        logger.info(f"Recorded sale: {ticker} (reason: {reason}, rank: {rank})")
        return record_id

    def check_reentry_allowed(self, ticker: str, current_rank: int = None) -> Tuple[bool, str]:
        """Check if a ticker can be re-entered based on cooldown rules

        Args:
            ticker: Stock ticker to check
            current_rank: Current rank in momentum list (1-15)

        Returns:
            Tuple of (allowed, reason)
        """
        from datetime import datetime

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get most recent non-rebought sale
        adapter.execute(cursor, '''
            SELECT sold_date, sold_reason, sold_rank, can_rebuy_after
            FROM sold_positions
            WHERE ticker = ? AND rebought = 0
            ORDER BY sold_date DESC
            LIMIT 1
        ''', (ticker,))

        row = adapter.fetchone_dict(cursor)
        conn.close()

        if not row:
            # Never sold or already rebought - OK to buy
            return True, "No active cooldown"

        sold_date = datetime.fromisoformat(row['sold_date'])
        sold_reason = row['sold_reason']
        can_rebuy_after = datetime.fromisoformat(row['can_rebuy_after'])
        now = datetime.now()

        # Check time-based cooldown
        if now < can_rebuy_after:
            days_remaining = (can_rebuy_after - now).days
            return False, f"Cooldown active ({days_remaining} days remaining)"

        # Additional check for top_3 sales
        if sold_reason == 'top_3' and current_rank is not None:
            # Must have dropped to rank 9-13 (positions 9-13 in top 15)
            if current_rank < 9:
                return False, f"Rank too high ({current_rank}), must drop to 9-13"

        return True, "Cooldown expired, OK to rebuy"

    def mark_rebought(self, ticker: str) -> None:
        """Mark a ticker as rebought (clear cooldown)

        Args:
            ticker: Stock ticker that was rebought
        """
        from datetime import datetime

        conn = self.get_connection()
        cursor = conn.cursor()

        adapter.execute(cursor, '''
            UPDATE sold_positions
            SET rebought = 1, rebought_date = ?
            WHERE ticker = ? AND rebought = 0
        ''', (datetime.now().isoformat(), ticker))

        conn.commit()
        conn.close()

        logger.info(f"Marked {ticker} as rebought")

    def get_cooldown_stocks(self) -> List[Dict[str, Any]]:
        """Get list of stocks currently in cooldown

        Returns:
            List of dicts with cooldown info
        """
        from datetime import datetime

        conn = self.get_connection()
        cursor = conn.cursor()

        adapter.execute(cursor, '''
            SELECT ticker, sold_date, sold_reason, sold_rank, can_rebuy_after
            FROM sold_positions
            WHERE rebought = 0
            ORDER BY sold_date DESC
        ''')

        rows = adapter.fetchall_dict(cursor)
        conn.close()

        now = datetime.now()
        cooldowns = []

        for row in rows:
            can_rebuy_after = datetime.fromisoformat(row['can_rebuy_after'])
            days_remaining = max(0, (can_rebuy_after - now).days)

            cooldowns.append({
                'ticker': row['ticker'],
                'sold_date': row['sold_date'],
                'sold_reason': row['sold_reason'],
                'sold_rank': row['sold_rank'],
                'can_rebuy_after': row['can_rebuy_after'],
                'days_remaining': days_remaining,
                'can_rebuy': now >= can_rebuy_after
            })

        return cooldowns

    def lock_all_historical_snapshots(self, before_date: str = None) -> int:
        """Lock all snapshots before a given date to prevent modification

        Args:
            before_date: ISO date string (YYYY-MM-DD). If None, locks all existing snapshots

        Returns:
            Number of snapshots locked
        """
        from datetime import datetime

        conn = self.get_connection()
        cursor = conn.cursor()

        if before_date:
            adapter.execute(cursor, '''
                UPDATE portfolio_snapshots
                SET is_locked = 1
                WHERE timestamp < ? AND (is_locked = 0 OR is_locked IS NULL)
            ''', (before_date,))
        else:
            adapter.execute(cursor, '''
                UPDATE portfolio_snapshots
                SET is_locked = 1
                WHERE (is_locked = 0 OR is_locked IS NULL)
            ''')

        locked_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Locked {locked_count} historical snapshots")
        return locked_count

    def get_this_week_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get snapshot for current week (if exists)

        Returns:
            Snapshot dict if exists, None otherwise
        """
        from datetime import datetime, timedelta

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get start of this week (Monday)
        now = datetime.now()
        monday = now - timedelta(days=now.weekday())
        monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        adapter.execute(cursor, '''
            SELECT * FROM portfolio_snapshots
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (monday_start.isoformat(),))

        row = adapter.fetchone_dict(cursor)
        conn.close()

        if row:
            return {
                'id': row['id'],
                'timestamp': row['timestamp'],
                'take_profit': json.loads(row['take_profit']),
                'hold': json.loads(row['hold']),
                'buffer': json.loads(row['buffer']),
                'total_stocks': row['total_stocks'],
                'portfolio_value': row['portfolio_value'],
                'notes': row['notes'],
                'is_locked': row['is_locked']
            }
        return None

    def can_create_new_snapshot(self) -> Tuple[bool, str]:
        """Check if we can create a new snapshot this week

        Returns:
            Tuple of (allowed, reason)
        """
        from datetime import datetime

        # Check if snapshot already exists this week
        this_week_snapshot = self.get_this_week_snapshot()

        if this_week_snapshot:
            if this_week_snapshot['is_locked']:
                return False, "This week's snapshot is locked (historical data)"
            return False, f"Snapshot already exists for this week (ID: {this_week_snapshot['id']})"

        # Check if it's Monday (weekday 0)
        now = datetime.now()
        if now.weekday() != 0:
            return False, f"New snapshots can only be created on Monday (today is {now.strftime('%A')})"

        # Check if it's evening (after 18:00)
        if now.hour < 18:
            return False, f"New snapshots can only be created after 18:00 (current time: {now.strftime('%H:%M')})"

        return True, "OK - Can create new weekly snapshot"

    def record_trade(self, ticker: str, action: str, price: float, shares: float,
                     capital_allocated: float, rank: int = None, company_name: str = None,
                     strategy_note: str = None, metadata: Dict = None) -> int:
        """Record a trade execution

        Args:
            ticker: Stock ticker
            action: 'BUY' or 'SELL'
            price: Execution price per share
            shares: Number of shares
            capital_allocated: Capital allocated for this trade
            rank: Rank in screener (if applicable)
            company_name: Company full name
            strategy_note: Note about strategy
            metadata: Additional metadata dict

        Returns:
            Trade ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        total_cost = price * shares
        cash_remaining = capital_allocated - total_cost

        adapter.execute(cursor, '''
            INSERT INTO trades
            (ticker, company_name, action, rank, price, shares, capital_allocated,
             total_cost, cash_remaining, status, strategy_note, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticker,
            company_name,
            action,
            rank,
            price,
            shares,
            capital_allocated,
            total_cost,
            cash_remaining,
            'FILLED',
            strategy_note,
            json.dumps(metadata) if metadata else None
        ))

        trade_id = adapter.get_last_insert_id(cursor)
        conn.commit()
        conn.close()

        logger.info(f"Trade recorded: {action} {shares:.2f} shares of {ticker} @ ${price:.2f}")
        return trade_id

    def get_trades(self, limit: int = 50, ticker: str = None) -> List[Dict[str, Any]]:
        """Get trade history

        Args:
            limit: Max number of trades to return
            ticker: Filter by ticker (optional)

        Returns:
            List of trade dicts
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if ticker:
            adapter.execute(cursor, '''
                SELECT * FROM trades
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (ticker, limit))
        else:
            adapter.execute(cursor, '''
                SELECT * FROM trades
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

        rows = adapter.fetchall_dict(cursor)
        conn.close()

        trades = []
        for row in rows:
            trades.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'ticker': row['ticker'],
                'company_name': row['company_name'],
                'action': row['action'],
                'rank': row['rank'],
                'price': row['price'],
                'shares': row['shares'],
                'capital_allocated': row['capital_allocated'],
                'total_cost': row['total_cost'],
                'cash_remaining': row['cash_remaining'],
                'status': row['status'],
                'strategy_note': row['strategy_note'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else None
            })

        return trades


# Convenience function
def get_db() -> Database:
    """Get database instance

    Returns:
        Database instance
    """
    return Database()
