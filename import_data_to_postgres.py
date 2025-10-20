#!/usr/bin/env python3
"""
Import exported data to PostgreSQL database
Reads JSON backup and inserts into new database
"""

import json
import os
import sys
from database import Database

def import_data(json_file: str):
    """Import data from JSON backup to database

    Args:
        json_file: Path to JSON backup file
    """
    print("=" * 60)
    print("IMPORTING DATA TO DATABASE")
    print("=" * 60)
    print()

    # Check if using PostgreSQL
    if os.getenv('DATABASE_URL'):
        print(f"Target: PostgreSQL ({os.getenv('DATABASE_URL')[:30]}...)")
    else:
        print("Target: SQLite (portfolio.db)")
    print()

    # Load JSON data
    print(f"1. Loading data from {json_file}...")
    with open(json_file, 'r') as f:
        data = json.load(f)

    trades = data.get('trades', [])
    snapshots = data.get('portfolio_snapshots', [])
    logs = data.get('activity_log', [])

    print(f"   [OK] Loaded:")
    print(f"        - {len(trades)} trades")
    print(f"        - {len(snapshots)} snapshots")
    print(f"        - {len(logs)} activity log entries")
    print()

    # Initialize database
    print("2. Connecting to database...")
    db = Database()
    print("   [OK] Connected")
    print()

    # Import trades
    print("3. Importing trades...")
    conn = db.get_connection()
    cursor = conn.cursor()
    imported_trades = 0

    for trade in trades:
        try:
            db.record_trade(
                ticker=trade['ticker'],
                action=trade['action'],
                price=trade['price'],
                shares=trade['shares'],
                capital_allocated=trade['capital_allocated'],
                rank=trade.get('rank'),
                company_name=trade.get('company_name'),
                strategy_note=trade.get('strategy_note'),
                metadata=trade.get('metadata')
            )
            imported_trades += 1
        except Exception as e:
            print(f"   [WARNING] Failed to import trade {trade['ticker']}: {e}")

    conn.commit()
    print(f"   [OK] Imported {imported_trades}/{len(trades)} trades")
    print()

    # Import portfolio snapshots
    print("4. Importing portfolio snapshots...")
    imported_snapshots = 0

    for snapshot in snapshots:
        try:
            # Parse lists from JSON strings if needed
            take_profit = snapshot.get('take_profit', [])
            hold = snapshot.get('hold', [])
            buffer = snapshot.get('buffer', [])

            if isinstance(take_profit, str):
                take_profit = json.loads(take_profit)
            if isinstance(hold, str):
                hold = json.loads(hold)
            if isinstance(buffer, str):
                buffer = json.loads(buffer)

            db.save_portfolio_snapshot(
                take_profit=take_profit,
                hold=hold,
                buffer=buffer,
                notes=snapshot.get('notes'),
                portfolio_value=snapshot.get('portfolio_value'),
                is_locked=snapshot.get('is_locked', False),
                timestamp=snapshot.get('timestamp')
            )
            imported_snapshots += 1
        except Exception as e:
            print(f"   [WARNING] Failed to import snapshot: {e}")

    conn.commit()
    print(f"   [OK] Imported {imported_snapshots}/{len(snapshots)} snapshots")
    print()

    # Import activity log
    print("5. Importing activity log...")
    imported_logs = 0

    for log in logs:
        try:
            db.add_activity_log(
                action_type=log['action_type'],
                description=log['description'],
                ticker=log.get('ticker'),
                metadata=log.get('metadata')
            )
            imported_logs += 1
        except Exception as e:
            print(f"   [WARNING] Failed to import log entry: {e}")

    conn.commit()
    conn.close()
    print(f"   [OK] Imported {imported_logs}/{len(logs)} log entries")
    print()

    print("=" * 60)
    print("[SUCCESS] DATA IMPORT COMPLETE")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  - Trades imported: {imported_trades}/{len(trades)}")
    print(f"  - Snapshots imported: {imported_snapshots}/{len(snapshots)}")
    print(f"  - Log entries imported: {imported_logs}/{len(logs)}")
    print()


if __name__ == "__main__":
    # Find most recent backup file
    import glob
    backups = glob.glob("render_data_backup_*.json")

    if not backups:
        print("ERROR: No backup files found!")
        print("Run export_render_data.py first.")
        sys.exit(1)

    # Use most recent backup
    latest_backup = sorted(backups)[-1]
    print(f"Using backup: {latest_backup}")
    print()

    import_data(latest_backup)
