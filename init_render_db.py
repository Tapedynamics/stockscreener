#!/usr/bin/env python3
"""
Initialize PostgreSQL database on Render
Creates all required tables for the stock screener application
"""

import os
import sys
from dotenv import load_dotenv
from db_adapter import adapter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_database():
    """Initialize all database tables"""

    # Load environment variables
    load_dotenv()

    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    if not database_url.startswith('postgres'):
        logger.error("This script is for PostgreSQL only. DATABASE_URL must start with 'postgres'")
        sys.exit(1)

    logger.info(f"Connecting to PostgreSQL database...")
    logger.info(f"Database type: {adapter.db_type}")

    try:
        conn = adapter.get_connection()
        cursor = conn.cursor()

        logger.info("Creating portfolio_snapshots table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                take_profit TEXT NOT NULL,
                hold TEXT NOT NULL,
                buffer TEXT NOT NULL,
                total_stocks INTEGER,
                portfolio_value REAL,
                notes TEXT,
                is_locked BOOLEAN DEFAULT FALSE
            )
        ''')

        logger.info("Creating activity_log table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action_type TEXT NOT NULL,
                ticker TEXT,
                description TEXT NOT NULL,
                metadata TEXT
            )
        ''')

        logger.info("Creating stock_performance table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS stock_performance (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                price REAL,
                volume BIGINT,
                UNIQUE(ticker, date)
            )
        ''')

        logger.info("Creating trades table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                buy_price REAL,
                sell_price REAL,
                quantity INTEGER,
                trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id)
            )
        ''')

        logger.info("Creating sold_positions table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS sold_positions (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                buy_price REAL,
                sell_price REAL,
                sell_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hold_days INTEGER,
                profit_loss REAL,
                profit_loss_pct REAL,
                snapshot_id INTEGER,
                rebought BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id)
            )
        ''')

        logger.info("Creating settings table...")
        adapter.execute(cursor, '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        logger.info("✅ All tables created successfully!")

        # Verify tables exist
        logger.info("\nVerifying tables...")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        tables = cursor.fetchall()
        logger.info(f"Found {len(tables)} tables:")
        for table in tables:
            logger.info(f"  - {table[0]}")

        conn.close()
        logger.info("\n✅ Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("PostgreSQL Database Initialization Script")
    logger.info("="*60)
    init_database()
