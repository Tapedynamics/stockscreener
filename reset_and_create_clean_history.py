#!/usr/bin/env python3
"""
Reset database and create clean historical data from backtest

This script:
1. Deletes ALL existing snapshots, sales, and activity logs
2. Runs the backtest to generate 41 weeks of historical data
3. Locks all historical snapshots as immutable
"""

from database import get_db
from populate_from_backtest import populate_database_from_backtest

def main():
    print("\n" + "="*70)
    print("RESET DATABASE AND CREATE CLEAN HISTORICAL DATA")
    print("="*70)

    db = get_db()
    conn = db.get_connection()
    cursor = conn.cursor()

    # Step 1: Clear all existing data
    print("\nStep 1: Clearing ALL existing data...")
    cursor.execute("DELETE FROM portfolio_snapshots")
    deleted_snapshots = cursor.rowcount
    print(f"  Deleted {deleted_snapshots} snapshots")

    cursor.execute("DELETE FROM sold_positions")
    deleted_sales = cursor.rowcount
    print(f"  Deleted {deleted_sales} sales")

    cursor.execute("DELETE FROM activity_log")
    deleted_logs = cursor.rowcount
    print(f"  Deleted {deleted_logs} activity logs")

    conn.commit()
    conn.close()

    print("\nDatabase cleared successfully!")

    # Step 2: Populate with clean backtest data
    print("\n" + "="*70)
    print("Step 2: Populating with backtest data (Jan-Oct 2025)...")
    print("="*70)

    populate_database_from_backtest()

    # Step 3: Lock all snapshots as historical
    print("\n" + "="*70)
    print("Step 3: Locking all snapshots as historical data...")
    print("="*70)

    locked_count = db.lock_all_historical_snapshots()
    print(f"\n{locked_count} snapshots locked successfully")

    # Final verification
    history = db.get_portfolio_history(limit=100)
    locked = [s for s in history if s.get('is_locked')]

    print("\n" + "="*70)
    print("CLEAN HISTORICAL DATA CREATED SUCCESSFULLY")
    print("="*70)
    print(f"\nTotal snapshots: {len(history)}")
    print(f"Locked snapshots: {len(locked)}")
    print(f"Period: Jan 2025 - Oct 2025 (41 weeks)")
    print(f"\nAll historical data is now protected and immutable.")
    print(f"New snapshots can only be added on Monday evenings (after 18:00).")
    print("="*70 + "\n")

if __name__ == '__main__':
    try:
        print("\n" + "="*70)
        print("WARNING: This will DELETE ALL existing portfolio data")
        print("and create a clean historical backtest from scratch")
        print("="*70)

        response = input("\nProceed? (yes/no): ")

        if response.lower() == 'yes':
            main()
        else:
            print("\nCancelled - no changes made\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
