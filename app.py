#!/usr/bin/env python3
"""
Flask Web App per Stock Screener
"""

from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
import re
import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from database import get_db
from scheduler import create_scheduler
from price_tracker import get_price_tracker
from portfolio_simulator import get_simulator
from utils import api_response, api_error, api_success, validate_settings
from constants import (
    HTTP_REQUEST_TIMEOUT,
    HTTP_HEADERS,
    DEFAULT_INITIAL_VALUE,
    LOG_FORMAT,
    LOG_LEVEL
)
import atexit
from dotenv import load_dotenv
from populate_history_endpoint import history_bp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', LOG_LEVEL)),
    format=os.getenv('LOG_FORMAT', LOG_FORMAT)
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Register blueprints
app.register_blueprint(history_bp)

# URL del tuo screener Finviz (from environment or default)
FINVIZ_URL = os.getenv(
    'FINVIZ_URL',
    "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"
)

# Global scheduler instance
portfolio_scheduler = None


def get_finviz_stocks(url: str) -> list:
    """
    Scarica e parsifica la pagina Finviz per estrarre i ticker

    Args:
        url: URL del screener Finviz

    Returns:
        Lista dei ticker symbols
    """
    try:
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=HTTP_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        logger.info("Successfully fetched Finviz data")

        soup = BeautifulSoup(response.content, 'html.parser')

        tickers = []
        seen = set()

        # Trova tutti i link ai ticker
        all_links = soup.find_all('a', href=lambda x: x and 'quote.ashx?t=' in x)

        for link in all_links:
            href = link.get('href', '')

            # Estrai il ticker dal parametro t= nell'URL
            if '?t=' in href or '&t=' in href:
                match = re.search(r'[?&]t=([A-Z.-]+)', href)

                if match:
                    ticker = match.group(1)

                    if ticker not in seen:
                        tickers.append(ticker)
                        seen.add(ticker)

        logger.info(f"Extracted {len(tickers)} tickers")
        return tickers

    except requests.exceptions.Timeout:
        logger.error(f"Request timeout after {HTTP_REQUEST_TIMEOUT} seconds")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_finviz_stocks: {e}")
        return []


def organize_basket(tickers: list) -> dict:
    """
    Organizza i ticker in categorie

    Args:
        tickers: Lista di ticker symbols

    Returns:
        Dizionario con categorie portfolio
    """
    if len(tickers) < 15:
        logger.warning(f"Only {len(tickers)} tickers found, expected at least 15")

    basket = {
        'take_profit': tickers[0:3],
        'hold': tickers[3:13],
        'buffer': tickers[13:15],
        'total_found': len(tickers)
    }

    return basket


def automated_screener_job():
    """
    Automated screener job for scheduler
    Returns dict with success status
    """
    try:
        db = get_db()

        # Run screener
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers:
            return {
                'success': False,
                'error': 'No tickers found'
            }

        # Organize basket
        top_15 = tickers[:15]
        basket = organize_basket(top_15)

        # Get previous portfolio
        previous_portfolio = db.get_latest_portfolio()

        # Save snapshot
        snapshot_id = db.save_portfolio_snapshot(
            basket['take_profit'],
            basket['hold'],
            basket['buffer'],
            notes='Automated weekly rebalance'
        )

        # Compare and log changes
        if previous_portfolio:
            changes = db.compare_portfolios(basket, previous_portfolio)

            if changes['added']:
                db.add_activity_log(
                    'BUY',
                    f"🤖 AI Agent: Added {len(changes['added'])} new positions: {', '.join(changes['added'][:3])}{'...' if len(changes['added']) > 3 else ''}",
                    metadata={'tickers': changes['added'], 'automated': True}
                )

            if changes['removed']:
                db.add_activity_log(
                    'SELL',
                    f"🤖 AI Agent: Removed {len(changes['removed'])} positions: {', '.join(changes['removed'][:3])}{'...' if len(changes['removed']) > 3 else ''}",
                    metadata={'tickers': changes['removed'], 'automated': True}
                )

            for move in changes['moved']:
                db.add_activity_log(
                    'REBALANCE',
                    f"🤖 AI Agent: {move['ticker']} moved from {move['from']} to {move['to']}",
                    ticker=move['ticker'],
                    metadata={**move, 'automated': True}
                )

            if not changes['added'] and not changes['removed'] and not changes['moved']:
                db.add_activity_log(
                    'HOLD',
                    '🤖 AI Agent: Automated rebalance - No changes needed, all positions maintained',
                    metadata={'automated': True}
                )

        # Always log the automated scan
        db.add_activity_log(
            'SCAN',
            f'🤖 AI Agent: Automated weekly scan completed - {basket["total_found"]} stocks identified',
            metadata={'total': basket['total_found'], 'automated': True}
        )

        return {
            'success': True,
            'total_stocks': basket['total_found'],
            'snapshot_id': snapshot_id
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.route('/')
def index():
    """Pagina principale"""
    return render_template('index.html')


@app.route('/chart')
def chart():
    """Pagina dedicata ai grafici"""
    return render_template('chart.html')


@app.route('/api/screener', methods=['GET'])
def run_screener():
    """API endpoint per eseguire lo screener"""
    logger.info("Running screener manually...")

    try:
        db = get_db()

        # Estrai i ticker
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers:
            logger.error("No tickers found from screener")
            return api_error('Nessun ticker trovato', 500)

        # Prendi i primi 15
        top_15 = tickers[:15]

        # Organizza in basket
        basket = organize_basket(top_15)

        # Get previous portfolio
        previous_portfolio = db.get_latest_portfolio()

        # Save new portfolio snapshot
        snapshot_id = db.save_portfolio_snapshot(
            basket['take_profit'],
            basket['hold'],
            basket['buffer'],
            notes='Manual screener run'
        )

        # Compare portfolios and log changes
        if previous_portfolio:
            changes = db.compare_portfolios(basket, previous_portfolio)

            # Log additions
            if changes['added']:
                db.add_activity_log(
                    'BUY',
                    f"Added {len(changes['added'])} new positions: {', '.join(changes['added'][:3])}{'...' if len(changes['added']) > 3 else ''}",
                    metadata={'tickers': changes['added']}
                )

            # Log removals
            if changes['removed']:
                db.add_activity_log(
                    'SELL',
                    f"Removed {len(changes['removed'])} positions: {', '.join(changes['removed'][:3])}{'...' if len(changes['removed']) > 3 else ''}",
                    metadata={'tickers': changes['removed']}
                )

            # Log position changes
            for move in changes['moved']:
                db.add_activity_log(
                    'REBALANCE',
                    f"{move['ticker']} moved from {move['from']} to {move['to']}",
                    ticker=move['ticker'],
                    metadata=move
                )

            # Log if no changes
            if not changes['added'] and not changes['removed'] and not changes['moved']:
                db.add_activity_log(
                    'HOLD',
                    'Portfolio maintained - All stocks still meet quality criteria'
                )
        else:
            # First run
            db.add_activity_log(
                'INIT',
                f'Initial portfolio created with {basket["total_found"]} stocks',
                metadata={'count': basket['total_found']}
            )

        # Always log the scan
        db.add_activity_log(
            'SCAN',
            f'AI Agent analyzed Finviz screener and identified {basket["total_found"]} high-potential stocks matching criteria',
            metadata={'total': basket['total_found']}
        )

        # Get performance data for stocks
        tracker = get_price_tracker()
        stock_performance = tracker.update_portfolio_prices(basket)

        logger.info(f"Screener completed successfully - {basket['total_found']} stocks found")

        return api_success({
            'basket': basket,
            'snapshot_id': snapshot_id,
            'performance': stock_performance
        })

    except Exception as e:
        logger.error(f"Error in run_screener: {e}", exc_info=True)
        return api_error(str(e), 500)


@app.route('/api/activity-log', methods=['GET'])
def get_activity_log():
    """Get activity log entries"""
    try:
        db = get_db()
        logs = db.get_activity_log(limit=20)

        return api_success(logs)

    except Exception as e:
        logger.error(f"Error in get_activity_log: {e}")
        return api_error(str(e), 500)


@app.route('/api/portfolio/history', methods=['GET'])
def get_portfolio_history():
    """Get portfolio history"""
    try:
        db = get_db()
        history = db.get_portfolio_history(limit=10)

        return api_success(history)

    except Exception as e:
        logger.error(f"Error in get_portfolio_history: {e}")
        return api_error(str(e), 500)


@app.route('/api/portfolio/latest', methods=['GET'])
def get_latest_portfolio():
    """Get latest portfolio snapshot"""
    try:
        db = get_db()
        portfolio = db.get_latest_portfolio()

        if portfolio:
            return api_success(portfolio)
        else:
            return api_error('No portfolio found', 404)

    except Exception as e:
        logger.error(f"Error in get_latest_portfolio: {e}")
        return api_error(str(e), 500)


@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get scheduler status"""
    try:
        global portfolio_scheduler

        if portfolio_scheduler:
            status = portfolio_scheduler.get_status()
            return api_success(status)
        else:
            return api_error('Scheduler not initialized', 500)

    except Exception as e:
        logger.error(f"Error in get_scheduler_status: {e}")
        return api_error(str(e), 500)


@app.route('/api/portfolio/performance', methods=['GET'])
def get_portfolio_performance():
    """Get portfolio performance with real prices"""
    try:
        db = get_db()
        tracker = get_price_tracker()

        # Get latest portfolio
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return api_error('No portfolio found', 404)

        # Calculate stats with real prices
        stats = tracker.get_portfolio_stats({
            'take_profit': portfolio['take_profit'],
            'hold': portfolio['hold'],
            'buffer': portfolio['buffer']
        })

        return api_success(stats)

    except Exception as e:
        logger.error(f"Error in get_portfolio_performance: {e}")
        return api_error(str(e), 500)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all settings"""
    try:
        db = get_db()

        # Default settings
        default_settings = {
            'scheduler_day': 'mon',
            'scheduler_time': '19:00',
            'scheduler_timezone': 'Europe/Rome',
            'initial_value': '150000',
            'take_profit_count': '3',
            'hold_count': '10',
            'buffer_count': '2',
            'notify_rebalance': 'false',
            'notify_changes': 'true'
        }

        # Get saved settings from database
        settings = {}
        for key in default_settings.keys():
            value = db.get_setting(key, default_settings[key])
            settings[key] = value

        return api_success(settings)

    except Exception as e:
        logger.error(f"Error in get_settings: {e}")
        return api_error(str(e), 500)


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save settings with validation"""
    logger.info("Saving settings...")

    try:
        db = get_db()
        data = request.get_json()

        if not data:
            logger.warning("No data provided in settings request")
            return api_error('No data provided', 400)

        # Validate all settings
        is_valid, error_msg, sanitized_data = validate_settings(data)

        if not is_valid:
            logger.warning(f"Settings validation failed: {error_msg}")
            return api_error(f'Validation error: {error_msg}', 400)

        # Save each validated setting
        for key, value in sanitized_data.items():
            db.set_setting(key, str(value))
            logger.debug(f"Saved setting: {key} = {value}")

        logger.info(f"Successfully saved {len(sanitized_data)} settings")

        return api_success({
            'message': 'Settings saved successfully',
            'count': len(sanitized_data)
        })

    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        return api_error(str(e), 500)


@app.route('/api/portfolio/chart', methods=['GET'])
def get_portfolio_chart():
    """Get portfolio chart data from real historical snapshots"""
    try:
        db = get_db()

        # Get timeframe parameter (default: ALL)
        timeframe = request.args.get('timeframe', 'ALL')

        # Get ALL portfolio history (no limit)
        history = db.get_portfolio_history(limit=100)

        if not history or len(history) == 0:
            return api_error('No portfolio history found', 404)

        logger.info(f"Building chart with {len(history)} historical snapshots")

        # Build chart data from real history
        labels = []
        portfolio_counts = []

        # Reverse to get chronological order (oldest first)
        history_sorted = sorted(history, key=lambda x: x['timestamp'])

        for snapshot in history_sorted:
            # Parse timestamp
            timestamp = snapshot['timestamp']
            if 'T' not in timestamp:
                # SQL format: convert to readable
                from datetime import datetime as dt
                date_obj = dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                label = date_obj.strftime('%b %d')
            else:
                # ISO format
                from datetime import datetime as dt
                date_obj = dt.fromisoformat(timestamp.replace('Z', '+00:00'))
                label = date_obj.strftime('%b %d')

            labels.append(label)
            portfolio_counts.append(snapshot['total_stocks'])

        # Calculate portfolio value based on position count (simplified)
        # In reality you'd use actual stock prices
        initial_value = float(db.get_setting('initial_value', '150000'))
        value_per_position = initial_value / 15  # Average per stock

        portfolio_values = [count * value_per_position for count in portfolio_counts]

        chart_data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Portfolio Value ($)',
                    'data': portfolio_values,
                    'borderColor': '#00ff88',
                    'backgroundColor': 'rgba(0, 255, 136, 0.1)',
                    'tension': 0.4,
                    'fill': True
                },
                {
                    'label': 'Total Positions',
                    'data': portfolio_counts,
                    'borderColor': '#00d4ff',
                    'backgroundColor': 'rgba(0, 212, 255, 0.1)',
                    'tension': 0.4,
                    'fill': True,
                    'yAxisID': 'y1'
                }
            ]
        }

        return api_success({
            'chart_data': chart_data,
            'timeframe': timeframe,
            'snapshots_count': len(history_sorted)
        })

    except Exception as e:
        logger.error(f"Error in get_portfolio_chart: {e}", exc_info=True)
        return api_error(str(e), 500)


def init_scheduler():
    """Initialize the scheduler (only in main worker)"""
    global portfolio_scheduler

    # Only initialize scheduler in development or in single-worker production
    # In Gunicorn with multiple workers, scheduler should run separately
    worker_id = os.getenv('WORKER_ID', '0')
    is_main_worker = worker_id == '0'

    if not is_main_worker and os.getenv('GUNICORN_WORKERS'):
        logger.info(f"Skipping scheduler init - Worker {worker_id} (non-main)")
        return

    try:
        portfolio_scheduler = create_scheduler(automated_screener_job)
        logger.info("✅ Automated scheduler initialized - Weekly rebalance at Monday 19:00 CET")

        # Register shutdown handler
        atexit.register(lambda: portfolio_scheduler.stop() if portfolio_scheduler else None)

    except Exception as e:
        logger.error(f"❌ Failed to initialize scheduler: {e}")


def check_and_populate_history():
    """Check if database is empty and populate with historical data"""
    try:
        db = get_db()
        snapshots = db.get_portfolio_history(limit=5)

        if len(snapshots) < 5:
            logger.info("Database has few snapshots, generating historical data...")

            # Import and run the generator
            try:
                from generate_history import generate_historical_data
                generate_historical_data()
                logger.info("Historical data generated successfully!")
            except Exception as e:
                logger.error(f"Error generating historical data: {e}")
    except Exception as e:
        logger.error(f"Error checking database: {e}")


if __name__ == '__main__':
    logger.info("="*50)
    logger.info("AI Portfolio Manager - Development Mode")
    logger.info("="*50)
    logger.info("Server starting on: http://localhost:5000")

    # Check and populate history if needed
    check_and_populate_history()

    # Initialize scheduler in development
    init_scheduler()

    logger.info("Press CTRL+C to stop the server")

    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For production (Gunicorn)
    # Check and populate history on startup
    check_and_populate_history()

    # Only init scheduler if explicitly enabled or running single worker
    if os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true':
        init_scheduler()
    else:
        logger.info("Scheduler disabled in production (set ENABLE_SCHEDULER=true to enable)")
