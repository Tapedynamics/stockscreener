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


@history_bp.route('/api/admin/populate-history', methods=['POST'])
def populate_history():
    """Manually trigger historical data generation"""
    try:
        logger.info("Manual history population requested")

        db = get_db()
        existing = len(db.get_portfolio_history(limit=100))

        if existing >= 40:
            return {
                'success': False,
                'error': f'Database already has {existing} snapshots. Clear database first if you want to regenerate.',
                'existing_count': existing
            }, 400

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
