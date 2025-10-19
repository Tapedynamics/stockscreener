#!/usr/bin/env python3
"""
Flask Web App per Stock Screener
"""

from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from database import get_db
from scheduler import create_scheduler
from price_tracker import get_price_tracker
import atexit

app = Flask(__name__)

# URL del tuo screener Finviz
FINVIZ_URL = "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"

# Global scheduler instance
portfolio_scheduler = None


def get_finviz_stocks(url):
    """
    Scarica e parsifica la pagina Finviz per estrarre i ticker
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

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

        return tickers

    except Exception as e:
        print(f"Errore: {e}")
        return []


def organize_basket(tickers):
    """
    Organizza i ticker in categorie
    """
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


@app.route('/api/screener', methods=['GET'])
def run_screener():
    """API endpoint per eseguire lo screener"""
    try:
        db = get_db()

        # Estrai i ticker
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers:
            return jsonify({
                'success': False,
                'error': 'Nessun ticker trovato'
            }), 500

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

        return jsonify({
            'success': True,
            'data': basket,
            'snapshot_id': snapshot_id,
            'performance': stock_performance
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/activity-log', methods=['GET'])
def get_activity_log():
    """Get activity log entries"""
    try:
        db = get_db()
        logs = db.get_activity_log(limit=20)

        return jsonify({
            'success': True,
            'data': logs
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/history', methods=['GET'])
def get_portfolio_history():
    """Get portfolio history"""
    try:
        db = get_db()
        history = db.get_portfolio_history(limit=10)

        return jsonify({
            'success': True,
            'data': history
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/latest', methods=['GET'])
def get_latest_portfolio():
    """Get latest portfolio snapshot"""
    try:
        db = get_db()
        portfolio = db.get_latest_portfolio()

        if portfolio:
            return jsonify({
                'success': True,
                'data': portfolio
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No portfolio found'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get scheduler status"""
    try:
        global portfolio_scheduler

        if portfolio_scheduler:
            status = portfolio_scheduler.get_status()
            return jsonify({
                'success': True,
                'data': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/performance', methods=['GET'])
def get_portfolio_performance():
    """Get portfolio performance with real prices"""
    try:
        db = get_db()
        tracker = get_price_tracker()

        # Get latest portfolio
        portfolio = db.get_latest_portfolio()

        if not portfolio:
            return jsonify({
                'success': False,
                'error': 'No portfolio found'
            }), 404

        # Calculate stats with real prices
        stats = tracker.get_portfolio_stats({
            'take_profit': portfolio['take_profit'],
            'hold': portfolio['hold'],
            'buffer': portfolio['buffer']
        })

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def init_scheduler():
    """Initialize the scheduler"""
    global portfolio_scheduler

    try:
        portfolio_scheduler = create_scheduler(automated_screener_job)
        print("✅ Automated scheduler initialized - Weekly rebalance at Monday 19:00 CET")

        # Register shutdown handler
        atexit.register(lambda: portfolio_scheduler.stop() if portfolio_scheduler else None)

    except Exception as e:
        print(f"❌ Failed to initialize scheduler: {e}")


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 AI Portfolio Manager")
    print("="*50)
    print("\nServer in esecuzione su: http://localhost:5000")

    # Initialize scheduler
    init_scheduler()

    print("Premi CTRL+C per fermare il server\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For production (Gunicorn)
    init_scheduler()
