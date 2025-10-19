#!/usr/bin/env python3
"""
Simple endpoint to manually trigger history generation
Useful for production environments like Render.com
"""

from flask import Blueprint
from database import get_db
import logging

logger = logging.getLogger(__name__)

# Create blueprint
history_bp = Blueprint('history', __name__)


@history_bp.route('/api/admin/clear-history', methods=['POST'])
def clear_history():
    """Clear all historical data (for regeneration)"""
    try:
        logger.info("Manual history clear requested")

        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()

        # Count before deletion
        cursor.execute('SELECT COUNT(*) FROM portfolio_snapshots')
        snapshots_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM activity_log')
        logs_count = cursor.fetchone()[0]

        # Delete all data
        cursor.execute('DELETE FROM portfolio_snapshots')
        cursor.execute('DELETE FROM activity_log')
        cursor.execute('DELETE FROM stock_performance')

        conn.commit()
        conn.close()

        logger.info(f"Cleared {snapshots_count} snapshots and {logs_count} log entries")

        return {
            'success': True,
            'message': 'All historical data cleared',
            'deleted_snapshots': snapshots_count,
            'deleted_logs': logs_count
        }, 200

    except Exception as e:
        logger.error(f"Error clearing history: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }, 500


@history_bp.route('/api/admin/populate-history', methods=['POST'])
def populate_history():
    """Manually trigger historical data generation"""
    try:
        logger.info("Manual history population requested")

        db = get_db()
        existing = len(db.get_portfolio_history(limit=100))

        # Remove the 40 limit check to allow regeneration
        logger.info(f"Starting historical data generation (existing: {existing} snapshots)")

        # Import and run generator
        from generate_history import generate_historical_data

        logger.info(f"Starting historical data generation (existing: {existing} snapshots)")
        generate_historical_data()

        new_count = len(db.get_portfolio_history(limit=100))
        logger.info(f"Historical data generated: {new_count} total snapshots")

        return {
            'success': True,
            'message': f'Successfully generated historical data',
            'snapshots_before': existing,
            'snapshots_after': new_count,
            'generated': new_count - existing
        }, 200

    except Exception as e:
        logger.error(f"Error populating history: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }, 500
