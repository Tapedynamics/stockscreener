#!/usr/bin/env python3
"""
Lock all historical portfolio snapshots to prevent modification

This script locks all existing snapshots in the database, marking them as
immutable historical data from the backtest period (Jan-Oct 2025).
"""

from database import get_db
from datetime import datetime

def main():
    print("\n" + "="*70)
    print("LOCKING HISTORICAL PORTFOLIO SNAPSHOTS")
    print("="*70)

    db = get_db()

    # Get current snapshot count
    history = db.get_portfolio_history(limit=100)
    total_snapshots = len(history)

    print(f"\nTotal snapshots in database: {total_snapshots}")

    # Lock all existing snapshots
    print("\nLocking all snapshots as historical data...")
    locked_count = db.lock_all_historical_snapshots()

    print(f"\n{locked_count} snapshots locked successfully")
    print("\nThese snapshots are now protected and cannot be modified.")
    print("New snapshots can only be added on Monday evenings (after 18:00).")

    print("\n" + "="*70)
    print("PROTECTION ENABLED")
    print("="*70 + "\n")

if __name__ == '__main__':
    try:
        response = input("Lock all historical snapshots? (yes/no): ")
        if response.lower() == 'yes':
            main()
        else:
            print("\nCancelled - no changes made\n")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
