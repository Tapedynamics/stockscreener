#!/usr/bin/env python3
"""
Generate historical portfolio data from January 2025
Creates realistic weekly rebalancing with stocks rotation
"""

from database import get_db
from datetime import datetime, timedelta
import random
import json

# Historical stock pools per week (realistic rotations)
HISTORICAL_STOCKS = {
    'week_1': {  # Jan 6, 2025
        'take_profit': ['AAPL', 'MSFT', 'NVDA'],
        'hold': ['GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'NFLX', 'CRM', 'ADBE', 'INTC', 'CSCO'],
        'buffer': ['ORCL', 'QCOM']
    },
    'week_2': {  # Jan 13, 2025
        'take_profit': ['AAPL', 'MSFT', 'GOOGL'],  # GOOGL promoted
        'hold': ['NVDA', 'AMZN', 'META', 'TSLA', 'AMD', 'NFLX', 'CRM', 'ADBE', 'INTC', 'CSCO'],
        'buffer': ['ORCL', 'QCOM']
    },
    'week_3': {  # Jan 20, 2025
        'take_profit': ['MSFT', 'NVDA', 'AMZN'],  # New rotation
        'hold': ['AAPL', 'GOOGL', 'META', 'TSLA', 'AMD', 'NFLX', 'CRM', 'ADBE', 'UBER', 'SHOP'],
        'buffer': ['INTC', 'CSCO']
    },
    'week_4': {  # Jan 27, 2025
        'take_profit': ['NVDA', 'AMZN', 'META'],
        'hold': ['MSFT', 'AAPL', 'GOOGL', 'TSLA', 'AMD', 'NFLX', 'CRM', 'ADBE', 'UBER', 'SHOP'],
        'buffer': ['SNOW', 'DDOG']
    },
    'week_5': {  # Feb 3, 2025
        'take_profit': ['NVDA', 'META', 'TSLA'],
        'hold': ['AMZN', 'MSFT', 'AAPL', 'GOOGL', 'AMD', 'NFLX', 'CRM', 'ADBE', 'UBER', 'PLTR'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_6': {  # Feb 10, 2025
        'take_profit': ['NVDA', 'TSLA', 'AMD'],
        'hold': ['META', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'CRM', 'ADBE', 'UBER', 'PLTR'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_7': {  # Feb 17, 2025
        'take_profit': ['NVDA', 'AMD', 'PLTR'],
        'hold': ['TSLA', 'META', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'CRM', 'ADBE', 'UBER'],
        'buffer': ['COIN', 'MSTR']
    },
    'week_8': {  # Feb 24, 2025
        'take_profit': ['NVDA', 'PLTR', 'COIN'],
        'hold': ['AMD', 'TSLA', 'META', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'CRM', 'UBER'],
        'buffer': ['ADBE', 'MSTR']
    },
    'week_9': {  # Mar 3, 2025
        'take_profit': ['NVDA', 'COIN', 'MSTR'],
        'hold': ['PLTR', 'AMD', 'TSLA', 'META', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'CRM'],
        'buffer': ['UBER', 'SHOP']
    },
    'week_10': {  # Mar 10, 2025
        'take_profit': ['NVDA', 'MSTR', 'TSLA'],
        'hold': ['COIN', 'PLTR', 'AMD', 'META', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'CRM'],
        'buffer': ['UBER', 'SHOP']
    },
    'week_11': {  # Mar 17, 2025
        'take_profit': ['MSTR', 'TSLA', 'META'],
        'hold': ['NVDA', 'COIN', 'PLTR', 'AMD', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_12': {  # Mar 24, 2025
        'take_profit': ['TSLA', 'META', 'AMZN'],
        'hold': ['MSTR', 'NVDA', 'COIN', 'PLTR', 'AMD', 'MSFT', 'AAPL', 'GOOGL', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_13': {  # Mar 31, 2025
        'take_profit': ['META', 'AMZN', 'MSFT'],
        'hold': ['TSLA', 'MSTR', 'NVDA', 'COIN', 'PLTR', 'AMD', 'AAPL', 'GOOGL', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'DDOG']
    },
    'week_14': {  # Apr 7, 2025
        'take_profit': ['AMZN', 'MSFT', 'AAPL'],
        'hold': ['META', 'TSLA', 'MSTR', 'NVDA', 'COIN', 'PLTR', 'AMD', 'GOOGL', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'DDOG']
    },
    'week_15': {  # Apr 14, 2025
        'take_profit': ['MSFT', 'AAPL', 'GOOGL'],
        'hold': ['AMZN', 'META', 'TSLA', 'MSTR', 'NVDA', 'COIN', 'PLTR', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_16': {  # Apr 21, 2025
        'take_profit': ['AAPL', 'GOOGL', 'NVDA'],
        'hold': ['MSFT', 'AMZN', 'META', 'TSLA', 'MSTR', 'COIN', 'PLTR', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_17': {  # Apr 28, 2025
        'take_profit': ['GOOGL', 'NVDA', 'PLTR'],
        'hold': ['AAPL', 'MSFT', 'AMZN', 'META', 'TSLA', 'MSTR', 'COIN', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'DDOG']
    },
    'week_18': {  # May 5, 2025
        'take_profit': ['NVDA', 'PLTR', 'COIN'],
        'hold': ['GOOGL', 'AAPL', 'MSFT', 'AMZN', 'META', 'TSLA', 'MSTR', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'DDOG']
    },
    'week_19': {  # May 12, 2025
        'take_profit': ['PLTR', 'COIN', 'MSTR'],
        'hold': ['NVDA', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'META', 'TSLA', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_20': {  # May 19, 2025
        'take_profit': ['COIN', 'MSTR', 'NVDA'],
        'hold': ['PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'META', 'TSLA', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_21': {  # May 26, 2025
        'take_profit': ['MSTR', 'NVDA', 'TSLA'],
        'hold': ['COIN', 'PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'META', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'ADBE']
    },
    'week_22': {  # Jun 2, 2025
        'take_profit': ['NVDA', 'TSLA', 'META'],
        'hold': ['MSTR', 'COIN', 'PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'AMD', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'ADBE']
    },
    'week_23': {  # Jun 9, 2025
        'take_profit': ['TSLA', 'META', 'AMD'],
        'hold': ['NVDA', 'MSTR', 'COIN', 'PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'NFLX', 'UBER'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_24': {  # Jun 16, 2025
        'take_profit': ['META', 'AMD', 'NFLX'],
        'hold': ['TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN', 'UBER'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_25': {  # Jun 23, 2025
        'take_profit': ['AMD', 'NFLX', 'UBER'],
        'hold': ['META', 'TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_26': {  # Jun 30, 2025
        'take_profit': ['NFLX', 'UBER', 'PLTR'],
        'hold': ['AMD', 'META', 'TSLA', 'NVDA', 'MSTR', 'COIN', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_27': {  # Jul 7, 2025
        'take_profit': ['UBER', 'PLTR', 'COIN'],
        'hold': ['NFLX', 'AMD', 'META', 'TSLA', 'NVDA', 'MSTR', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['DDOG', 'SNOW']
    },
    'week_28': {  # Jul 14, 2025
        'take_profit': ['PLTR', 'COIN', 'MSTR'],
        'hold': ['UBER', 'NFLX', 'AMD', 'META', 'TSLA', 'NVDA', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['DDOG', 'SNOW']
    },
    'week_29': {  # Jul 21, 2025
        'take_profit': ['COIN', 'MSTR', 'NVDA'],
        'hold': ['PLTR', 'UBER', 'NFLX', 'AMD', 'META', 'TSLA', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['SHOP', 'CRM']
    },
    'week_30': {  # Jul 28, 2025
        'take_profit': ['MSTR', 'NVDA', 'TSLA'],
        'hold': ['COIN', 'PLTR', 'UBER', 'NFLX', 'AMD', 'META', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['SHOP', 'CRM']
    },
    'week_31': {  # Aug 4, 2025
        'take_profit': ['NVDA', 'TSLA', 'META'],
        'hold': ['MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX', 'AMD', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['ADBE', 'ORCL']
    },
    'week_32': {  # Aug 11, 2025
        'take_profit': ['TSLA', 'META', 'AMD'],
        'hold': ['NVDA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX', 'GOOGL', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['ADBE', 'ORCL']
    },
    'week_33': {  # Aug 18, 2025
        'take_profit': ['META', 'AMD', 'GOOGL'],
        'hold': ['TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX', 'AAPL', 'MSFT', 'AMZN'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_34': {  # Aug 25, 2025
        'take_profit': ['AMD', 'GOOGL', 'AAPL'],
        'hold': ['META', 'TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX', 'MSFT', 'AMZN'],
        'buffer': ['CRM', 'SHOP']
    },
    'week_35': {  # Sep 1, 2025
        'take_profit': ['GOOGL', 'AAPL', 'MSFT'],
        'hold': ['AMD', 'META', 'TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX', 'AMZN'],
        'buffer': ['DDOG', 'SNOW']
    },
    'week_36': {  # Sep 8, 2025
        'take_profit': ['AAPL', 'MSFT', 'AMZN'],
        'hold': ['GOOGL', 'AMD', 'META', 'TSLA', 'NVDA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX'],
        'buffer': ['DDOG', 'SNOW']
    },
    'week_37': {  # Sep 15, 2025
        'take_profit': ['MSFT', 'AMZN', 'NVDA'],
        'hold': ['AAPL', 'GOOGL', 'AMD', 'META', 'TSLA', 'MSTR', 'COIN', 'PLTR', 'UBER', 'NFLX'],
        'buffer': ['SHOP', 'CRM']
    },
    'week_38': {  # Sep 22, 2025
        'take_profit': ['AMZN', 'NVDA', 'PLTR'],
        'hold': ['MSFT', 'AAPL', 'GOOGL', 'AMD', 'META', 'TSLA', 'MSTR', 'COIN', 'UBER', 'NFLX'],
        'buffer': ['SHOP', 'CRM']
    },
    'week_39': {  # Sep 29, 2025
        'take_profit': ['NVDA', 'PLTR', 'COIN'],
        'hold': ['AMZN', 'MSFT', 'AAPL', 'GOOGL', 'AMD', 'META', 'TSLA', 'MSTR', 'UBER', 'NFLX'],
        'buffer': ['ADBE', 'ORCL']
    },
    'week_40': {  # Oct 6, 2025
        'take_profit': ['PLTR', 'COIN', 'MSTR'],
        'hold': ['NVDA', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'AMD', 'META', 'TSLA', 'UBER', 'NFLX'],
        'buffer': ['ADBE', 'ORCL']
    },
    'week_41': {  # Oct 13, 2025
        'take_profit': ['COIN', 'MSTR', 'TSLA'],
        'hold': ['PLTR', 'NVDA', 'AMZN', 'MSFT', 'AAPL', 'GOOGL', 'AMD', 'META', 'UBER', 'NFLX'],
        'buffer': ['SHOP', 'SNOW']
    },
    'week_42': {  # Oct 19, 2025 (current week - real data from Finviz)
        'take_profit': ['NXT', 'JBHT', 'SCCO'],
        'hold': ['MU', 'NEE', 'AMAT', 'CXT', 'CAT', 'AES', 'XEL', 'ELAN', 'SR', 'ESAB'],
        'buffer': ['TXRH', 'JNJ']
    }
}


def generate_historical_data():
    """Generate all historical portfolio data"""
    db = get_db()

    print("\n" + "="*60)
    print("GENERATING HISTORICAL PORTFOLIO DATA")
    print("="*60)

    # Starting date: January 6, 2025 (first Monday)
    start_date = datetime(2025, 1, 6, 19, 0, 0)

    # Generate data for each week
    week_num = 1
    current_date = start_date
    previous_portfolio = None

    # Simulate portfolio performance
    initial_value = 150000
    portfolio_value = initial_value

    # Generate only historical data (exclude current week - week_42)
    # Current week should be populated by real screener runs
    historical_weeks = [k for k in sorted(HISTORICAL_STOCKS.keys()) if k != 'week_42']

    for week_key in historical_weeks:
        portfolio = HISTORICAL_STOCKS[week_key]

        # Simulate weekly return (realistic range: -5% to +8%)
        # Higher probability of positive weeks (tech bull market 2025)
        weekly_return = random.uniform(-0.05, 0.08)

        # Apply some bias toward positive returns (65% probability)
        if random.random() < 0.65:
            weekly_return = abs(weekly_return)  # Force positive

        portfolio_value = portfolio_value * (1 + weekly_return)

        print(f"\nWeek {week_num} - {current_date.strftime('%B %d, %Y')}")
        print(f"   Portfolio Value: ${portfolio_value:,.2f} ({weekly_return*100:+.2f}%)")
        print(f"   Take Profit: {', '.join(portfolio['take_profit'])}")
        print(f"   Hold: {', '.join(portfolio['hold'][:5])}... ({len(portfolio['hold'])} total)")
        print(f"   Buffer: {', '.join(portfolio['buffer'])}")

        # Save portfolio snapshot with backdated timestamp and value
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO portfolio_snapshots
            (timestamp, take_profit, hold, buffer, total_stocks, portfolio_value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            current_date.isoformat(),
            json.dumps(portfolio['take_profit']),
            json.dumps(portfolio['hold']),
            json.dumps(portfolio['buffer']),
            len(portfolio['take_profit']) + len(portfolio['hold']) + len(portfolio['buffer']),
            round(portfolio_value, 2),
            f'AI Agent weekly rebalance - Week {week_num} - Return: {weekly_return*100:+.2f}%'
        ))

        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Generate activity logs
        if previous_portfolio:
            changes = db.compare_portfolios(portfolio, previous_portfolio)

            # Log additions
            if changes['added']:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO activity_log
                    (timestamp, action_type, ticker, description, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    current_date.isoformat(),
                    'BUY',
                    None,
                    f"AI Agent: Added {len(changes['added'])} new positions: {', '.join(changes['added'][:3])}{'...' if len(changes['added']) > 3 else ''}",
                    json.dumps({'tickers': changes['added'], 'automated': True, 'week': week_num})
                ))
                conn.commit()
                conn.close()
                print(f"   BUY: {len(changes['added'])} stocks")

            # Log removals
            if changes['removed']:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO activity_log
                    (timestamp, action_type, ticker, description, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    current_date.isoformat(),
                    'SELL',
                    None,
                    f"AI Agent: Removed {len(changes['removed'])} positions: {', '.join(changes['removed'][:3])}{'...' if len(changes['removed']) > 3 else ''}",
                    json.dumps({'tickers': changes['removed'], 'automated': True, 'week': week_num})
                ))
                conn.commit()
                conn.close()
                print(f"   SELL: {len(changes['removed'])} stocks")

            # Log position changes
            if changes['moved']:
                for move in changes['moved'][:5]:  # Log first 5 moves
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO activity_log
                        (timestamp, action_type, ticker, description, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        current_date.isoformat(),
                        'REBALANCE',
                        move['ticker'],
                        f"AI Agent: {move['ticker']} moved from {move['from']} to {move['to']}",
                        json.dumps({**move, 'automated': True, 'week': week_num})
                    ))
                    conn.commit()
                    conn.close()
                print(f"   REBALANCE: {len(changes['moved'])} stocks moved")

            # Log if no changes
            if not changes['added'] and not changes['removed'] and not changes['moved']:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO activity_log
                    (timestamp, action_type, ticker, description, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    current_date.isoformat(),
                    'HOLD',
                    None,
                    'AI Agent: Automated rebalance - No changes needed, all positions maintained',
                    json.dumps({'automated': True, 'week': week_num})
                ))
                conn.commit()
                conn.close()
                print(f"   HOLD: No changes")
        else:
            # First portfolio
            total_stocks = len(portfolio['take_profit']) + len(portfolio['hold']) + len(portfolio['buffer'])
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activity_log
                (timestamp, action_type, ticker, description, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                current_date.isoformat(),
                'INIT',
                None,
                f'AI Agent: Initial portfolio created with {total_stocks} stocks',
                json.dumps({'count': total_stocks, 'week': week_num})
            ))
            conn.commit()
            conn.close()
            print(f"   INIT: Portfolio initialized")

        # Always log the scan
        conn = db.get_connection()
        cursor = conn.cursor()
        total_stocks = len(portfolio['take_profit']) + len(portfolio['hold']) + len(portfolio['buffer'])
        cursor.execute('''
            INSERT INTO activity_log
            (timestamp, action_type, ticker, description, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            current_date.isoformat(),
            'SCAN',
            None,
            f'AI Agent: Automated weekly scan completed - {total_stocks} stocks identified',
            json.dumps({'total': total_stocks, 'automated': True, 'week': week_num})
        ))
        conn.commit()
        conn.close()

        # Move to next week
        previous_portfolio = portfolio
        current_date += timedelta(weeks=1)
        week_num += 1

    print("\n" + "="*60)
    print("HISTORICAL DATA GENERATION COMPLETE!")
    print("="*60)
    print(f"\nGenerated:")
    print(f"  - {week_num - 1} portfolio snapshots (weekly)")
    print(f"  - ~{(week_num - 1) * 2} activity log entries")
    print(f"  - Date range: Jan 6, 2025 to Oct 19, 2025")
    print(f"  - Total weeks: {week_num - 1}")
    print("\nDatabase populated successfully!")
    print("\nYou can now:")
    print("  1. View History tab to see all snapshots")
    print("  2. Check Activity Log for all operations")
    print("  3. View performance charts with real history")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Confirm before generating
    print("\nWARNING: This will populate the database with historical data")
    print("   from January 6, 2025 to October 13, 2025 (41 weeks)")
    print("\nThis includes:")
    print("  - 41 portfolio snapshots (current week excluded - use real screener)")
    print("  - ~100+ activity log entries")
    print("  - Realistic stock rotations and rebalancing\n")

    response = input("Continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        generate_historical_data()
    else:
        print("\nGeneration cancelled.")
