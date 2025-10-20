#!/usr/bin/env python3
"""
Database Adapter - Automatic SQLite/PostgreSQL Support
Detects database type from environment and converts queries automatically
"""

import os
import logging
from typing import Any, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """Adapter that automatically handles SQLite and PostgreSQL differences"""

    def __init__(self):
        """Initialize adapter - detects database type from DATABASE_URL"""
        self.database_url = os.getenv('DATABASE_URL')

        if self.database_url and self.database_url.startswith('postgres'):
            self.db_type = 'postgresql'
            import psycopg2
            import psycopg2.extras
            self.module = psycopg2
            self.extras = psycopg2.extras
            logger.info("Using PostgreSQL database")
        else:
            self.db_type = 'sqlite'
            import sqlite3
            self.module = sqlite3
            self.extras = None
            logger.info("Using SQLite database")

    def convert_query(self, query: str) -> str:
        """Convert SQLite query to PostgreSQL if needed

        Changes:
        - ? → %s (parameter placeholders)
        - AUTOINCREMENT → (removed, SERIAL handles it)
        - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
        - DATETIME → TIMESTAMP (PostgreSQL type)
        - BOOLEAN → BOOLEAN (same in both)
        - REAL → REAL (same in both)
        - TEXT → TEXT (same in both)
        """
        if self.db_type == 'sqlite':
            return query

        # PostgreSQL conversions
        converted = query

        # Replace INTEGER PRIMARY KEY AUTOINCREMENT with SERIAL PRIMARY KEY
        converted = converted.replace(
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            'SERIAL PRIMARY KEY'
        )

        # Replace DATETIME with TIMESTAMP (PostgreSQL doesn't have DATETIME)
        converted = converted.replace('DATETIME', 'TIMESTAMP')

        # Replace ? placeholders with %s
        converted = converted.replace('?', '%s')

        # Remove AUTOINCREMENT (handled by SERIAL)
        converted = converted.replace('AUTOINCREMENT', '')

        return converted

    def get_connection(self, db_path: str = 'portfolio.db'):
        """Get database connection

        Args:
            db_path: Path to SQLite database (ignored for PostgreSQL)

        Returns:
            Database connection
        """
        if self.db_type == 'postgresql':
            conn = self.module.connect(self.database_url)
            return conn
        else:
            conn = self.module.connect(db_path)
            conn.row_factory = self.module.Row
            return conn

    def cursor_to_dict(self, cursor, row) -> dict:
        """Convert cursor row to dictionary

        Args:
            cursor: Database cursor
            row: Row data

        Returns:
            Dictionary with column names as keys
        """
        if self.db_type == 'postgresql':
            if row is None:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        else:
            # SQLite Row already acts like dict
            if row is None:
                return None
            return dict(row)

    def execute(self, cursor, query: str, params: tuple = ()):
        """Execute query with automatic conversion

        Args:
            cursor: Database cursor
            query: SQL query
            params: Query parameters

        Returns:
            Cursor after execution
        """
        converted_query = self.convert_query(query)
        cursor.execute(converted_query, params)
        return cursor

    def fetchone_dict(self, cursor) -> Optional[dict]:
        """Fetch one row as dictionary

        Args:
            cursor: Database cursor

        Returns:
            Row as dictionary or None
        """
        row = cursor.fetchone()
        return self.cursor_to_dict(cursor, row)

    def fetchall_dict(self, cursor) -> list:
        """Fetch all rows as list of dictionaries

        Args:
            cursor: Database cursor

        Returns:
            List of rows as dictionaries
        """
        rows = cursor.fetchall()
        return [self.cursor_to_dict(cursor, row) for row in rows]

    def get_last_insert_id(self, cursor) -> int:
        """Get last inserted row ID

        Args:
            cursor: Database cursor

        Returns:
            Last insert ID
        """
        if self.db_type == 'postgresql':
            # PostgreSQL: get from RETURNING clause or currval
            return cursor.fetchone()[0]
        else:
            # SQLite: use lastrowid
            return cursor.lastrowid


# Global adapter instance
adapter = DatabaseAdapter()
