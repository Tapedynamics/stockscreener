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
from typing import Dict, Any, Tuple, List
import yfinance as yf
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


def calculate_momentum_rankings(tickers: list) -> Dict[str, Dict[str, Any]]:
    """
    Calculate 30-day momentum for list of tickers

    Args:
        tickers: List of stock tickers to rank

    Returns:
        Dict mapping ticker to {rank, performance, price_start, price_end}
    """
    try:
        if not tickers:
            logger.warning("No tickers provided for momentum calculation")
            return {}

        # Download 35 days of data (to ensure we have 30 trading days)
        data = yf.download(tickers, period='35d', progress=False, auto_adjust=True)

        if data.empty:
            logger.warning("No price data downloaded for momentum calculation")
            return {}

        # Get Close prices
        if 'Close' in data.columns:
            prices = data['Close']
        elif isinstance(data.columns, __import__('pandas').MultiIndex):
            prices = data['Close']
        else:
            prices = data

        # Calculate momentum for each ticker
        momentum_data = {}

        for ticker in tickers:
            try:
                if ticker in prices.columns:
                    stock_prices = prices[ticker].dropna()
                    if len(stock_prices) >= 2:
                        # Get first and last price
                        first_price = stock_prices.iloc[0]
                        last_price = stock_prices.iloc[-1]

                        # Calculate 30-day performance
                        performance = ((last_price - first_price) / first_price) * 100

                        momentum_data[ticker] = {
                            'performance': performance,
                            'price_start': float(first_price),
                            'price_end': float(last_price),
                            'days': len(stock_prices)
                        }
                        logger.debug(f"{ticker}: 30d performance = {performance:.2f}%")
                    else:
                        logger.warning(f"{ticker}: Insufficient price data for momentum")
                else:
                    logger.warning(f"{ticker}: Not found in price data")
            except Exception as e:
                logger.error(f"Error calculating momentum for {ticker}: {e}")

        # Rank tickers by performance (descending)
        sorted_tickers = sorted(
            momentum_data.items(),
            key=lambda x: x[1]['performance'],
            reverse=True
        )

        # Add rank to each ticker
        ranked_data = {}
        for rank, (ticker, data) in enumerate(sorted_tickers, 1):
            ranked_data[ticker] = {
                **data,
                'rank': rank
            }

        logger.info(f"Calculated momentum for {len(ranked_data)} tickers")
        return ranked_data

    except Exception as e:
        logger.error(f"Error calculating momentum rankings: {e}")
        return {}


def calculate_real_portfolio_value(tickers: list, initial_investment: float = 150000) -> float:
    """
    Calculate real portfolio value using Yahoo Finance prices

    Args:
        tickers: List of stock tickers
        initial_investment: Total initial investment amount

    Returns:
        Current portfolio value based on real prices
    """
    try:
        if not tickers:
            logger.warning("No tickers provided for portfolio value calculation")
            return initial_investment

        # Equal allocation per stock
        investment_per_stock = initial_investment / len(tickers)

        # Download current prices
        data = yf.download(tickers, period='5d', progress=False, auto_adjust=True)

        if data.empty:
            logger.warning("No price data downloaded from Yahoo Finance")
            return initial_investment

        # Get Close prices
        if 'Close' in data.columns:
            prices = data['Close']
        elif isinstance(data.columns, __import__('pandas').MultiIndex):
            prices = data['Close']
        else:
            prices = data

        # Get latest prices for each stock
        total_value = 0
        successful_tickers = 0

        for ticker in tickers:
            try:
                if ticker in prices.columns:
                    stock_prices = prices[ticker].dropna()
                    if len(stock_prices) >= 2:
                        # Get first and last price from the period
                        first_price = stock_prices.iloc[0]
                        last_price = stock_prices.iloc[-1]

                        # Calculate value for this stock
                        shares = investment_per_stock / first_price
                        current_value = shares * last_price
                        total_value += current_value
                        successful_tickers += 1
                        logger.debug(f"{ticker}: ${first_price:.2f} -> ${last_price:.2f}, Value: ${current_value:.2f}")
                    else:
                        # Not enough data, use initial investment
                        total_value += investment_per_stock
                        logger.warning(f"{ticker}: Insufficient price data, using initial value")
                else:
                    # Ticker not found, use initial investment
                    total_value += investment_per_stock
                    logger.warning(f"{ticker}: Not found in price data, using initial value")
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                total_value += investment_per_stock

        if successful_tickers == 0:
            logger.warning("No successful price lookups, returning initial investment")
            return initial_investment

        logger.info(f"Portfolio value calculated: ${total_value:,.2f} ({successful_tickers}/{len(tickers)} tickers)")
        return total_value

    except Exception as e:
        logger.error(f"Error calculating portfolio value: {e}")
        return initial_investment


def format_trade_ticket(trade: Dict) -> str:
    """Format trade as a readable ticket"""
    action_emoji = "🟢" if trade['action'] == 'BUY' else "🔴"
    status_emoji = "✅" if trade['status'] == 'FILLED' else "⏳"

    ticket = f"""
╔═══════════════════════════════════════════════════════════╗
║     {action_emoji} {trade['action']} ORDER #{trade['id']:03d} - {status_emoji} {trade['status']}
╠═══════════════════════════════════════════════════════════╣
║ Date/Time:  {trade['timestamp']}
║ Ticker:     {trade['ticker']}
║ Company:    {trade['company_name'] or 'N/A'}
║ Rank:       #{trade['rank'] if trade['rank'] else 'N/A'}
╠═══════════════════════════════════════════════════════════╣
║ Price:      ${trade['price']:.2f} per share
║ Shares:     {trade['shares']:.4f}
║ Capital:    ${trade['capital_allocated']:,.2f}
║ Total Cost: ${trade['total_cost']:,.2f}
║ Cash Left:  ${trade['cash_remaining']:.2f}
╠═══════════════════════════════════════════════════════════╣
║ Strategy:   {trade['strategy_note'] or 'N/A'}
╚═══════════════════════════════════════════════════════════╝
"""
    return ticket


def execute_trade(ticker: str, action: str, capital: float, rank: int, strategy_note: str, db) -> Dict[str, Any]:
    """
    Execute a trade with real-time price from Yahoo Finance

    Args:
        ticker: Stock ticker
        action: 'BUY' or 'SELL'
        capital: Capital allocated for trade
        rank: Rank in screener
        strategy_note: Strategy note
        db: Database instance

    Returns:
        Dict with trade details
    """
    try:
        # Fetch real-time price from Yahoo Finance
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get current price (try multiple fields)
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('ask')

        if not price:
            # Fallback: get latest close price
            hist = stock.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
            else:
                logger.error(f"Could not fetch price for {ticker}")
                return {'success': False, 'error': f'Price not available for {ticker}'}

        # Get company name
        company_name = info.get('shortName') or info.get('longName') or ticker

        # Calculate shares
        shares = capital / price

        # Record trade in database
        trade_id = db.record_trade(
            ticker=ticker,
            action=action,
            price=price,
            shares=shares,
            capital_allocated=capital,
            rank=rank,
            company_name=company_name,
            strategy_note=strategy_note,
            metadata={'source': 'yahoo_finance'}
        )

        # Log to activity log with clean format: "Bought AAPL @$182.45"
        action_text = "Bought" if action == "BUY" else "Sold"
        db.add_activity_log(
            action_type=action,
            description=f"{action_text} {ticker} @${price:.2f}",
            ticker=ticker,
            metadata={
                'price': price,
                'shares': shares,
                'total_cost': shares * price,
                'rank': rank,
                'trade_id': trade_id
            }
        )

        logger.info(f"✅ {action} executed: {ticker} - {shares:.2f} shares @ ${price:.2f} = ${shares * price:.2f}")

        return {
            'success': True,
            'trade_id': trade_id,
            'ticker': ticker,
            'company_name': company_name,
            'action': action,
            'price': price,
            'shares': shares,
            'total_cost': shares * price,
            'cash_remaining': capital - (shares * price)
        }

    except Exception as e:
        logger.error(f"Error executing trade for {ticker}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_weekly_rotation(current_holdings: List[str], screener_results: Dict, db) -> Dict[str, Any]:
    """
    Calculate weekly rotation based on new strategy:
    - Ranks 1-3 (TP): If CORE stock moves here → SELL (take profit)
    - Ranks 4-13 (CORE): Active positions
    - Ranks 14-15 (BUFFER): Ex-CORE stocks (maintain position, penchina)
    - Out of top 15: SELL
    - Re-entry: Only after 2 weeks cooldown + rank 9-13

    Args:
        current_holdings: List of currently owned tickers
        screener_results: Dict with {take_profit: [], hold: [], buffer: []}
        db: Database instance

    Returns:
        Dict with rotation actions
    """
    # Get all screened stocks with ranks
    screener_stocks = screener_results['take_profit'] + screener_results['hold'] + screener_results['buffer']

    # Assign ranks
    stock_ranks = {}
    for i, ticker in enumerate(screener_stocks, start=1):
        stock_ranks[ticker] = i

    to_sell = []
    to_buy = []
    to_buffer = []  # Stocks moving to panchina

    # Check each current holding
    for ticker in current_holdings:
        if ticker not in stock_ranks:
            # Stock dropped out of top 15 → SELL
            to_sell.append({
                'ticker': ticker,
                'reason': 'drop_out',
                'rank': None,
                'action': 'SELL - Dropped out of top 15'
            })
            continue

        rank = stock_ranks[ticker]

        if rank <= 3:
            # Moved to TAKE PROFIT zone → SELL
            to_sell.append({
                'ticker': ticker,
                'reason': 'top_3',
                'rank': rank,
                'action': 'SELL - Take Profit (moved to top 3)'
            })
        elif rank >= 14:
            # Moved to BUFFER zone (panchina) → MAINTAIN
            to_buffer.append({
                'ticker': ticker,
                'rank': rank,
                'action': 'BUFFER - Maintain position (panchina)'
            })
        # else: rank 4-13 → stay in CORE, no action needed

    # Calculate available slots
    target_size = 12
    holdings_after_sells = [t for t in current_holdings if t not in [s['ticker'] for s in to_sell]]
    slots_available = target_size - len(holdings_after_sells)

    logger.info(f"Rotation: {len(holdings_after_sells)} holdings after sells, {slots_available} slots available")

    # Find candidates to buy (CORE zone, ranks 4-13)
    buy_candidates = []
    for ticker in screener_results['hold']:  # Ranks 4-13
        if ticker in holdings_after_sells:
            continue  # Already holding

        rank = stock_ranks[ticker]

        # Check re-entry rules
        allowed, reason = db.check_reentry_allowed(ticker, rank)

        if allowed:
            buy_candidates.append({
                'ticker': ticker,
                'rank': rank,
                'reentry_status': reason
            })
        else:
            logger.debug(f"Skip {ticker}: {reason}")

    # Sort by rank (prefer lower ranks, but avoid top 3)
    buy_candidates.sort(key=lambda x: x['rank'])

    # Take top N candidates to fill slots
    to_buy = buy_candidates[:slots_available]

    logger.info(f"Rotation: Selling {len(to_sell)}, Buying {len(to_buy)}, Buffer {len(to_buffer)}")

    return {
        'to_sell': to_sell,
        'to_buy': to_buy,
        'to_buffer': to_buffer,
        'slots_available': slots_available,
        'current_holdings': current_holdings,
        'holdings_after': holdings_after_sells
    }


def calculate_rotation_trades(current_portfolio: Dict, all_tickers: List[str], portfolio_size: int = 12) -> Dict[str, Any]:
    """
    Calculate momentum rotation trade suggestions

    Args:
        current_portfolio: Current portfolio dict with take_profit, hold, buffer
        all_tickers: List of all tickers from screener (top 15+)
        portfolio_size: Target portfolio size (default 12)

    Returns:
        Dict with {to_sell: [...], to_buy: [...], rankings: {...}}
    """
    db = get_db()

    # Get current holdings
    current_holdings = (current_portfolio.get('take_profit', []) +
                       current_portfolio.get('hold', []) +
                       current_portfolio.get('buffer', []))

    # Calculate momentum rankings for all tickers
    logger.info(f"Calculating momentum for {len(all_tickers)} tickers...")
    rankings = calculate_momentum_rankings(all_tickers)

    if not rankings:
        logger.warning("No momentum rankings available")
        return {'to_sell': [], 'to_buy': [], 'rankings': {}}

    # Get top 15 by momentum
    sorted_tickers = sorted(rankings.items(), key=lambda x: x[1]['rank'])
    top_15 = [t[0] for t in sorted_tickers[:15]]

    logger.info(f"Top 15 by momentum: {', '.join(top_15[:5])}... (showing first 5)")

    # Determine sells
    to_sell = []

    # Rule 1: Sell top 3 ranked stocks from current holdings
    holdings_with_ranks = [(ticker, rankings[ticker]['rank'])
                           for ticker in current_holdings
                           if ticker in rankings and rankings[ticker]['rank'] <= 15]
    holdings_with_ranks.sort(key=lambda x: x[1])  # Sort by rank

    for ticker, rank in holdings_with_ranks[:3]:  # Top 3
        if ticker in current_holdings:
            to_sell.append({
                'ticker': ticker,
                'reason': 'top_3',
                'rank': rank,
                'performance': rankings[ticker]['performance']
            })
            logger.info(f"Sell {ticker} (top 3, rank #{rank})")

    # Rule 2: Sell stocks that dropped out of top 15
    for ticker in current_holdings:
        if ticker not in top_15:
            rank = rankings.get(ticker, {}).get('rank', 999)
            if ticker not in [s['ticker'] for s in to_sell]:  # Don't double-count
                to_sell.append({
                    'ticker': ticker,
                    'reason': 'drop_out',
                    'rank': rank,
                    'performance': rankings.get(ticker, {}).get('performance', 0)
                })
                logger.info(f"Sell {ticker} (dropped out, rank #{rank})")

    # Calculate how many new stocks we need to buy
    holdings_after_sells = [t for t in current_holdings if t not in [s['ticker'] for s in to_sell]]
    slots_to_fill = portfolio_size - len(holdings_after_sells)

    logger.info(f"Current: {len(current_holdings)}, After sells: {len(holdings_after_sells)}, Slots to fill: {slots_to_fill}")

    # Determine buys with re-entry rules
    to_buy = []
    candidates = []

    for ticker in top_15:
        if ticker in holdings_after_sells:
            continue  # Already holding

        rank = rankings[ticker]['rank']

        # Check re-entry rules
        allowed, reason = db.check_reentry_allowed(ticker, rank)

        if allowed:
            # Prefer ranks 4-13 (after top 3)
            if rank >= 4:
                candidates.append({
                    'ticker': ticker,
                    'rank': rank,
                    'performance': rankings[ticker]['performance'],
                    'reentry_reason': reason
                })
                logger.debug(f"Buy candidate: {ticker} (rank #{rank})")
        else:
            logger.debug(f"Skip {ticker}: {reason}")

    # Sort candidates by rank (prefer lower ranks within 4-13)
    candidates.sort(key=lambda x: x['rank'])

    # Take the top N candidates
    to_buy = candidates[:slots_to_fill]

    for buy in to_buy:
        logger.info(f"Buy {buy['ticker']} (rank #{buy['rank']})")

    return {
        'to_sell': to_sell,
        'to_buy': to_buy,
        'rankings': rankings,
        'top_15': top_15,
        'current_holdings': current_holdings,
        'slots_to_fill': slots_to_fill
    }


def automated_screener_job():
    """
    Automated screener job for scheduler
    Simply calls the main run_screener endpoint logic
    Returns dict with success status
    """
    logger.info("🤖 Automated screener job triggered by scheduler")

    # Call the main screener endpoint (this will handle all logic)
    # We create a mock request context to call it
    from flask import Flask
    with app.test_request_context():
        try:
            response = run_screener()
            # Extract JSON from response
            if hasattr(response, 'get_json'):
                result = response.get_json()
            else:
                result = response

            logger.info(f"🤖 Automated job completed: {result.get('success', False)}")
            return result
        except Exception as e:
            logger.error(f"🤖 Automated job failed: {str(e)}")
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


@app.route('/history')
def history():
    """Pagina dedicata allo storico portfolio"""
    return render_template('history.html')


@app.route('/settings')
def settings():
    """Pagina dedicata alle impostazioni"""
    return render_template('settings.html')


@app.route('/compare')
def compare():
    """Pagina dedicata al confronto snapshot"""
    return render_template('compare.html')


@app.route('/benchmark')
def benchmark():
    """Pagina dedicata al benchmark S&P 500"""
    return render_template('benchmark.html')


@app.route('/orders')
def orders():
    """Pagina dedicata agli ordini"""
    return render_template('orders.html')


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

        # Check if we can create a new snapshot (protected historical data + weekly limit)
        from datetime import datetime, timedelta
        can_create, reason = db.can_create_new_snapshot()

        # Calculate portfolio value
        initial_value = float(db.get_setting('initial_value', '150000'))
        target_portfolio_size = 12  # Target: 12 stocks total

        # FIRST RUN: Only buy CORE positions (hold = positions 4-13)
        # Capital per stock = $150,000 / 12 = $12,500
        # Week 1: Buy 10 CORE = $125,000 deployed
        # Week 2: Rotation cycle to reach 12 stocks
        is_first_run = (previous_portfolio is None)

        if is_first_run:
            # First order: only 10 CORE stocks
            active_tickers = basket['hold']  # Positions 4-13
            capital_per_stock = initial_value / target_portfolio_size  # $12,500 each
            logger.info(f"FIRST RUN: Buying {len(active_tickers)} CORE positions @ ${capital_per_stock:,.0f} each")

            # Execute BUY trades for each CORE position
            trade_results = []
            for i, ticker in enumerate(active_tickers, start=4):  # Ranks 4-13
                trade = execute_trade(
                    ticker=ticker,
                    action='BUY',
                    capital=capital_per_stock,
                    rank=i,
                    strategy_note='First Order - Week 1 CORE',
                    db=db
                )
                trade_results.append(trade)

            rotation_result = None
        else:
            # Subsequent runs: weekly rotation strategy
            current_holdings = previous_portfolio['hold']  # Currently owned stocks
            capital_per_stock = initial_value / target_portfolio_size

            # Calculate rotation (sells, buys, buffer movements)
            rotation_result = calculate_weekly_rotation(current_holdings, basket, db)

            # Execute SELL trades
            for sell in rotation_result['to_sell']:
                # Get current shares owned (would need position tracking, for now use capital)
                trade = execute_trade(
                    ticker=sell['ticker'],
                    action='SELL',
                    capital=capital_per_stock,  # Selling full position
                    rank=sell.get('rank'),
                    strategy_note=f"Rotation - {sell['reason']}",
                    db=db
                )
                db.record_sale(sell['ticker'], sell['reason'], sell.get('rank'))
                logger.info(f"SELL: {sell['ticker']} - {sell['action']}")

            # Execute BUY trades
            for buy in rotation_result['to_buy']:
                trade = execute_trade(
                    ticker=buy['ticker'],
                    action='BUY',
                    capital=capital_per_stock,
                    rank=buy['rank'],
                    strategy_note=f"Rotation - Re-entry rank {buy['rank']}",
                    db=db
                )
                db.mark_rebought(buy['ticker'])
                logger.info(f"BUY: {buy['ticker']} (rank {buy['rank']})")

            # Active tickers after rotation
            active_tickers = rotation_result['holdings_after'] + [b['ticker'] for b in rotation_result['to_buy']]

            logger.info(f"ROTATION COMPLETE: {len(active_tickers)} stocks active, {len(rotation_result['to_buffer'])} in buffer")

        # Calculate value only for active positions
        new_portfolio_value = calculate_real_portfolio_value(active_tickers, capital_per_stock * len(active_tickers))

        snapshot_id = None

        # Prepare snapshot data based on actual ownership
        if is_first_run:
            # First run: save CORE as owned, TP and Buffer are screener references
            snapshot_tp = basket['take_profit']
            snapshot_hold = active_tickers  # 10 CORE stocks we bought
            snapshot_buffer = []  # No buffer yet
        else:
            # Subsequent runs: reflect actual ownership and buffer
            snapshot_tp = basket['take_profit']  # Screener top 3 (for reference)
            snapshot_hold = active_tickers  # Stocks we currently own
            snapshot_buffer = [b['ticker'] for b in rotation_result['to_buffer']]  # Stocks in panchina

        if can_create:
            # Create new weekly snapshot
            snapshot_id = db.save_portfolio_snapshot(
                snapshot_tp,
                snapshot_hold,
                snapshot_buffer,
                notes='Weekly portfolio rotation (Monday)' if not is_first_run else 'First order - 10 CORE positions',
                portfolio_value=new_portfolio_value,
                is_locked=False  # New snapshots start unlocked, can be updated during the week
            )
            logger.info(f"New weekly snapshot created with ID: {snapshot_id} - Value: ${new_portfolio_value:,.2f}")
        else:
            # Cannot create snapshot - return reason
            if previous_portfolio:
                snapshot_id = previous_portfolio['id']
                logger.warning(f"Cannot create snapshot: {reason}")
            else:
                # First ever run - allow creating initial snapshot
                snapshot_id = db.save_portfolio_snapshot(
                    basket['take_profit'],
                    basket['hold'],
                    basket['buffer'],
                    notes='Initial portfolio setup',
                    portfolio_value=new_portfolio_value,
                    is_locked=False
                )
                logger.info(f"Initial portfolio snapshot created with ID: {snapshot_id}")

        # Compare portfolios and log changes
        if previous_portfolio:
            if rotation_result:
                # Log rotation-based changes
                for sell in rotation_result['to_sell']:
                    db.add_activity_log(
                        'SELL',
                        f"{sell['ticker']} - {sell['action']}",
                        ticker=sell['ticker'],
                        metadata={'reason': sell['reason'], 'rank': sell.get('rank')}
                    )

                for buy in rotation_result['to_buy']:
                    db.add_activity_log(
                        'BUY',
                        f"{buy['ticker']} - New CORE position (rank {buy['rank']})",
                        ticker=buy['ticker'],
                        metadata={'rank': buy['rank'], 'reentry': buy['reentry_status']}
                    )

                for buffer_stock in rotation_result['to_buffer']:
                    db.add_activity_log(
                        'REBALANCE',
                        f"{buffer_stock['ticker']} - Moved to BUFFER (panchina, rank {buffer_stock['rank']})",
                        ticker=buffer_stock['ticker'],
                        metadata={'rank': buffer_stock['rank']}
                    )

                # Summary log
                if not rotation_result['to_sell'] and not rotation_result['to_buy'] and not rotation_result['to_buffer']:
                    db.add_activity_log(
                        'HOLD',
                        f'Weekly rotation - No changes needed, {len(active_tickers)} positions maintained'
                    )
                else:
                    db.add_activity_log(
                        'REBALANCE',
                        f'Weekly rotation complete - Sold: {len(rotation_result["to_sell"])}, Bought: {len(rotation_result["to_buy"])}, Buffer: {len(rotation_result["to_buffer"])}',
                        metadata={
                            'sells': len(rotation_result['to_sell']),
                            'buys': len(rotation_result['to_buy']),
                            'buffer_moves': len(rotation_result['to_buffer']),
                            'final_size': len(active_tickers)
                        }
                    )
        else:
            # First run - buying only CORE positions
            core_tickers = basket['hold']
            capital_per_stock = initial_value / target_portfolio_size
            deployed_capital = capital_per_stock * len(core_tickers)

            db.add_activity_log(
                'BUY',
                f'FIRST ORDER: Buying {len(core_tickers)} CORE positions (ranks 4-13) @ ${capital_per_stock:,.0f} each = ${deployed_capital:,.0f} total',
                metadata={
                    'tickers': core_tickers,
                    'type': 'initial_order',
                    'count': len(core_tickers),
                    'capital_per_stock': capital_per_stock,
                    'deployed_capital': deployed_capital,
                    'reserved_capital': initial_value - deployed_capital
                }
            )
            db.add_activity_log(
                'INIT',
                f'Portfolio initialized - Target: {target_portfolio_size} stocks | Week 1: {len(core_tickers)} CORE bought | Reserved: ${(initial_value - deployed_capital):,.0f}',
                metadata={
                    'total_found': basket['total_found'],
                    'target_size': target_portfolio_size,
                    'core_bought': len(core_tickers),
                    'tp_reserved': len(basket['take_profit']),
                    'buffer_reserved': len(basket['buffer'])
                }
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
            'performance': stock_performance,
            'snapshot_created': can_create,
            'snapshot_status': reason if not can_create else 'New snapshot created',
            'portfolio_value': new_portfolio_value
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


@app.route('/api/admin/reset-database', methods=['POST'])
def reset_database():
    """
    ADMIN ENDPOINT: Reset all portfolio data
    Clears snapshots, trades, activity log, sold positions, stock performance
    Preserves settings
    """
    try:
        db = get_db()

        # Delete all data (keep settings)
        conn = db.get_connection()
        cursor = conn.cursor()

        # Count before deletion
        cursor.execute('SELECT COUNT(*) FROM portfolio_snapshots')
        snapshots = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM activity_log')
        logs = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM trades')
        trades = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM sold_positions')
        sold = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM stock_performance')
        performance = cursor.fetchone()[0]

        logger.info(f"🗑️  RESET DATABASE - Before: {snapshots} snapshots, {logs} logs, {trades} trades")

        # DELETE ALL DATA (keep settings)
        cursor.execute('DELETE FROM portfolio_snapshots')
        cursor.execute('DELETE FROM activity_log')
        cursor.execute('DELETE FROM stock_performance')
        cursor.execute('DELETE FROM sold_positions')
        cursor.execute('DELETE FROM trades')

        # Reset auto-increment counters
        cursor.execute('DELETE FROM sqlite_sequence WHERE name IN ("portfolio_snapshots", "activity_log", "stock_performance", "sold_positions", "trades")')

        conn.commit()

        # Verify deletion
        cursor.execute('SELECT COUNT(*) FROM portfolio_snapshots')
        snapshots_after = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM activity_log')
        logs_after = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM trades')
        trades_after = cursor.fetchone()[0]

        logger.info(f"✅ DATABASE RESET COMPLETE - After: {snapshots_after} snapshots, {logs_after} logs, {trades_after} trades")

        return api_success({
            'message': 'Database reset successful',
            'deleted': {
                'snapshots': snapshots,
                'activity_log': logs,
                'trades': trades,
                'sold_positions': sold,
                'stock_performance': performance
            },
            'verified': {
                'snapshots': snapshots_after,
                'activity_log': logs_after,
                'trades': trades_after
            }
        })

    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        return api_error(str(e), 500)


@app.route('/api/portfolio/refresh-prices', methods=['GET'])
def refresh_portfolio_prices():
    """Get real-time prices and calculate P&L for current portfolio"""
    try:
        db = get_db()

        # Get current portfolio
        latest = db.get_latest_portfolio()
        if not latest:
            return api_error('No portfolio found', 404)

        # Get all active positions (HOLD = CORE stocks we own)
        active_tickers = latest['hold']

        if not active_tickers:
            return api_error('No active positions', 400)

        # Get all BUY trades to know purchase prices and shares
        all_trades = db.get_trades(limit=1000)
        buy_trades = [t for t in all_trades if t['action'] == 'BUY' and t['ticker'] in active_tickers]

        # Group by ticker (latest buy for each)
        positions = {}
        for trade in buy_trades:
            ticker = trade['ticker']
            if ticker not in positions:
                positions[ticker] = {
                    'ticker': ticker,
                    'purchase_price': trade['price'],
                    'shares': trade['shares'],
                    'invested': trade['total_cost'],
                    'purchase_date': trade['timestamp']
                }

        # Fetch current prices
        results = []
        total_invested = 0
        total_current_value = 0

        for ticker, pos in positions.items():
            try:
                # Fetch real-time price
                stock = yf.Ticker(ticker)
                info = stock.info

                current_price = info.get('currentPrice') or info.get('regularMarketPrice')

                if not current_price:
                    # Fallback to latest close
                    hist = stock.history(period='1d')
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])

                if current_price:
                    current_value = pos['shares'] * current_price
                    pnl_dollars = current_value - pos['invested']
                    pnl_percent = (pnl_dollars / pos['invested']) * 100

                    results.append({
                        'ticker': ticker,
                        'company_name': info.get('shortName', ticker),
                        'shares': pos['shares'],
                        'purchase_price': pos['purchase_price'],
                        'current_price': current_price,
                        'invested': pos['invested'],
                        'current_value': current_value,
                        'pnl_dollars': pnl_dollars,
                        'pnl_percent': pnl_percent,
                        'purchase_date': pos['purchase_date']
                    })

                    total_invested += pos['invested']
                    total_current_value += current_value

            except Exception as e:
                logger.error(f"Error fetching price for {ticker}: {e}")
                results.append({
                    'ticker': ticker,
                    'error': str(e)
                })

        # Calculate total P&L
        total_pnl_dollars = total_current_value - total_invested
        total_pnl_percent = (total_pnl_dollars / total_invested * 100) if total_invested > 0 else 0

        return api_success({
            'positions': results,
            'summary': {
                'total_invested': total_invested,
                'total_current_value': total_current_value,
                'total_pnl_dollars': total_pnl_dollars,
                'total_pnl_percent': total_pnl_percent,
                'position_count': len(results),
                'updated_at': datetime.now().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error refreshing portfolio prices: {e}")
        return api_error(str(e), 500)


@app.route('/api/trades', methods=['GET'])
def get_trades_api():
    """Get trade history (order tickets)"""
    try:
        db = get_db()
        limit = request.args.get('limit', 50, type=int)
        ticker = request.args.get('ticker', None, type=str)

        trades = db.get_trades(limit=limit, ticker=ticker)

        return api_success({
            'trades': trades,
            'count': len(trades)
        })

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return api_error(str(e), 500)


@app.route('/api/trades/<int:trade_id>', methods=['GET'])
def get_trade_ticket(trade_id):
    """Get detailed trade ticket"""
    try:
        db = get_db()
        trades = db.get_trades(limit=1000)  # Get all and filter

        trade = next((t for t in trades if t['id'] == trade_id), None)

        if not trade:
            return api_error('Trade not found', 404)

        # Format trade ticket
        ticket = format_trade_ticket(trade)

        return api_success({
            'trade': trade,
            'ticket': ticket
        })

    except Exception as e:
        logger.error(f"Error fetching trade ticket: {e}")
        return api_error(str(e), 500)


@app.route('/api/portfolio/history', methods=['GET'])
def get_portfolio_history():
    """Get portfolio history"""
    try:
        db = get_db()
        history = db.get_portfolio_history(limit=10)

        # Return empty array if no history
        if history is None:
            history = []

        return api_success(history)

    except Exception as e:
        logger.error(f"Error in get_portfolio_history: {e}", exc_info=True)
        # Return empty array on error to prevent frontend crash
        return api_success([])


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
    """Get portfolio performance stats from historical data"""
    try:
        db = get_db()

        # Get latest portfolio
        latest = db.get_latest_portfolio()

        if not latest:
            # Return default empty stats
            return api_success({
                'total_value': 150000,
                'total_positions': 0,
                'weekly_performance': 0,
                'weekly_gain': 0,
                'all_time_return': 0,
                'all_time_gain': 0
            })

        # Get historical data for calculations
        history = db.get_portfolio_history(limit=100)

        if not history or len(history) == 0:
            # No historical data, return current snapshot
            current_value = latest.get('portfolio_value', 150000)
            return api_success({
                'total_value': current_value,
                'total_positions': latest['total_stocks'],
                'weekly_performance': 0,
                'weekly_gain': 0,
                'all_time_return': 0,
                'all_time_gain': 0
            })

        # Sort history chronologically (oldest first)
        history_sorted = sorted(history, key=lambda x: x['timestamp'])

        # Get first and latest values
        first_snapshot = history_sorted[0]
        latest_snapshot = history_sorted[-1]

        initial_value = first_snapshot.get('portfolio_value') or 150000
        current_value = latest_snapshot.get('portfolio_value') or initial_value

        # Calculate all-time return
        all_time_gain = current_value - initial_value
        all_time_return = ((current_value - initial_value) / initial_value * 100) if initial_value > 0 else 0

        # Calculate weekly return (find snapshot from ~7 days ago)
        weekly_gain = 0
        weekly_performance = 0
        if len(history_sorted) >= 2:
            from datetime import datetime, timedelta

            # Parse latest timestamp
            latest_time = latest_snapshot['timestamp']
            if 'T' in latest_time:
                latest_dt = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
            else:
                latest_dt = datetime.strptime(latest_time, '%Y-%m-%d %H:%M:%S')

            # Find snapshot from ~7 days ago
            week_ago = latest_dt - timedelta(days=7)
            week_ago_snapshot = None

            # Search for closest snapshot to 7 days ago
            for snapshot in reversed(history_sorted[:-1]):  # Exclude latest
                snap_time = snapshot['timestamp']
                if 'T' in snap_time:
                    snap_dt = datetime.fromisoformat(snap_time.replace('Z', '+00:00'))
                else:
                    snap_dt = datetime.strptime(snap_time, '%Y-%m-%d %H:%M:%S')

                # If this snapshot is older than or equal to 7 days ago, use it
                if snap_dt <= week_ago:
                    week_ago_snapshot = snapshot
                    break

            # If no snapshot from 7 days ago, use first snapshot
            if not week_ago_snapshot:
                week_ago_snapshot = history_sorted[0]

            previous_value = week_ago_snapshot.get('portfolio_value') or current_value
            weekly_gain = current_value - previous_value
            weekly_performance = ((current_value - previous_value) / previous_value * 100) if previous_value > 0 else 0

        return api_success({
            'total_value': round(current_value, 2),
            'total_positions': latest_snapshot['total_stocks'],
            'weekly_performance': round(weekly_performance, 2),
            'weekly_gain': round(weekly_gain, 2),
            'all_time_return': round(all_time_return, 2),
            'all_time_gain': round(all_time_gain, 2)
        })

    except Exception as e:
        logger.error(f"Error in get_portfolio_performance: {e}", exc_info=True)
        # Return default values on error
        return api_success({
            'total_value': 150000,
            'total_positions': 0,
            'weekly_performance': 0,
            'weekly_gain': 0,
            'all_time_return': 0,
            'all_time_gain': 0
        })


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
            # Return empty chart data instead of error
            return api_success({
                'chart_data': {
                    'labels': [],
                    'datasets': []
                },
                'timeframe': timeframe,
                'snapshots_count': 0
            })

        logger.info(f"Building chart with {len(history)} historical snapshots for timeframe: {timeframe}")

        # Build chart data from real history
        labels = []
        portfolio_counts = []

        # Reverse to get chronological order (oldest first)
        history_sorted = sorted(history, key=lambda x: x['timestamp'])

        # Filter by timeframe
        from datetime import datetime as dt, timedelta
        now = dt.now()

        if timeframe == '1M':
            cutoff_date = now - timedelta(days=30)
        elif timeframe == '3M':
            cutoff_date = now - timedelta(days=90)
        elif timeframe == '6M':
            cutoff_date = now - timedelta(days=180)
        elif timeframe == 'YTD':
            # Year to date - start of 2025
            cutoff_date = dt(2025, 1, 1)
        elif timeframe == '1Y':
            cutoff_date = now - timedelta(days=365)
        else:  # ALL
            cutoff_date = None

        # Filter history if cutoff date is set
        if cutoff_date:
            filtered_history = []
            for snapshot in history_sorted:
                timestamp = snapshot['timestamp']
                if 'T' not in timestamp:
                    date_obj = dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                else:
                    date_obj = dt.fromisoformat(timestamp.replace('Z', '+00:00'))

                if date_obj >= cutoff_date:
                    filtered_history.append(snapshot)

            history_sorted = filtered_history
            logger.info(f"Filtered to {len(history_sorted)} snapshots after {cutoff_date.strftime('%Y-%m-%d')}")

        if len(history_sorted) == 0:
            # No data in this timeframe
            return api_success({
                'chart_data': {
                    'labels': [],
                    'datasets': []
                },
                'timeframe': timeframe,
                'snapshots_count': 0
            })

        portfolio_values = []
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

            # Use portfolio_value from database if available, otherwise calculate
            if snapshot.get('portfolio_value'):
                portfolio_values.append(float(snapshot['portfolio_value']))
            else:
                # Fallback calculation for old data without portfolio_value
                initial_value = float(db.get_setting('initial_value', '150000'))
                value_per_position = initial_value / 15
                portfolio_values.append(snapshot['total_stocks'] * value_per_position)

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
        # Check if database is empty (first ever run)
        db = get_db()
        history = db.get_portfolio_history(limit=1)
        is_first_ever_run = (len(history) == 0)

        # If first run, schedule for today at 19:00
        portfolio_scheduler = create_scheduler(
            automated_screener_job,
            run_today_at_19=is_first_ever_run
        )

        if is_first_ever_run:
            logger.info("🎯 FIRST ORDER will run TODAY at 19:00 CET")

        logger.info("✅ Automated scheduler initialized - Weekly rebalance at Monday 19:00 CET")

        # Register shutdown handler
        atexit.register(lambda: portfolio_scheduler.stop() if portfolio_scheduler else None)

    except Exception as e:
        logger.error(f"❌ Failed to initialize scheduler: {e}")


def check_and_populate_history():
    """Check if database is empty and populate with historical data"""
    # DISABLED: We're starting fresh with real trades
    # Only use this for testing/demo purposes
    pass


@app.route('/api/rotation/suggest', methods=['GET'])
def get_rotation_suggestions():
    """Get momentum rotation trade suggestions"""
    try:
        db = get_db()

        # Get current portfolio
        current_portfolio = db.get_latest_portfolio()

        if not current_portfolio:
            return api_success({
                'to_sell': [],
                'to_buy': [],
                'message': 'No current portfolio found'
            })

        # Get top tickers from screener
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers or len(tickers) < 15:
            return api_error('Insufficient tickers from screener', 400)

        # Calculate rotation trades
        rotation = calculate_rotation_trades(current_portfolio, tickers[:20], portfolio_size=12)

        return api_success({
            'to_sell': rotation['to_sell'],
            'to_buy': rotation['to_buy'],
            'top_15': rotation['top_15'],
            'current_holdings': rotation['current_holdings'],
            'slots_to_fill': rotation['slots_to_fill'],
            'total_sells': len(rotation['to_sell']),
            'total_buys': len(rotation['to_buy'])
        })

    except Exception as e:
        logger.error(f"Error getting rotation suggestions: {e}", exc_info=True)
        return api_error(str(e), 500)


@app.route('/api/rotation/cooldown', methods=['GET'])
def get_cooldown_stocks():
    """Get list of stocks in cooldown period"""
    try:
        db = get_db()
        cooldowns = db.get_cooldown_stocks()

        return api_success({
            'cooldowns': cooldowns,
            'total': len(cooldowns)
        })

    except Exception as e:
        logger.error(f"Error getting cooldown stocks: {e}", exc_info=True)
        return api_error(str(e), 500)


@app.route('/api/rotation/rankings', methods=['GET'])
def get_momentum_rankings():
    """Get momentum rankings for current screener results"""
    try:
        # Get tickers from screener
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers or len(tickers) < 15:
            return api_error('Insufficient tickers from screener', 400)

        # Calculate momentum
        rankings = calculate_momentum_rankings(tickers[:20])

        # Convert to list sorted by rank
        ranked_list = sorted(
            [{'ticker': k, **v} for k, v in rankings.items()],
            key=lambda x: x['rank']
        )

        return api_success({
            'rankings': ranked_list,
            'total': len(ranked_list)
        })

    except Exception as e:
        logger.error(f"Error getting momentum rankings: {e}", exc_info=True)
        return api_error(str(e), 500)


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
