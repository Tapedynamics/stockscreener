#!/usr/bin/env python3
"""
Check if baseline data was saved correctly
"""

from database import get_db

db = get_db()

print("\n" + "="*70)
print("BASELINE DATA VERIFICATION")
print("="*70)

# Check settings
print("\n1. Settings Table:")
print(f"   baseline_ytd_2025_return: {db.get_setting('baseline_ytd_2025_return')}")
print(f"   baseline_ytd_2025_value: {db.get_setting('baseline_ytd_2025_value')}")
print(f"   baseline_ytd_2025_gain: {db.get_setting('baseline_ytd_2025_gain')}")
print(f"   baseline_ytd_2025_period_start: {db.get_setting('baseline_ytd_2025_period_start')}")
print(f"   baseline_ytd_2025_period_end: {db.get_setting('baseline_ytd_2025_period_end')}")
print(f"   baseline_snapshot_id: {db.get_setting('baseline_snapshot_id')}")

# Check snapshot
print("\n2. Baseline Snapshot:")
snapshot_id = db.get_setting('baseline_snapshot_id')
if snapshot_id:
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM portfolio_snapshots WHERE id = ?', (snapshot_id,))
    row = cursor.fetchone()
    if row:
        print(f"   ID: {row['id']}")
        print(f"   Timestamp: {row['timestamp']}")
        print(f"   Portfolio Value: ${row['portfolio_value']}")
        print(f"   Total Stocks: {row['total_stocks']}")
        print(f"   Notes: {row['notes']}")
    else:
        print("   [NOT FOUND]")
    conn.close()
else:
    print("   [NO SNAPSHOT ID SAVED]")

# Check stock performance
print("\n3. Stock Performance Table:")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM stock_performance WHERE date = '2025-10-19'")
count = cursor.fetchone()['count']
print(f"   Records with date 2025-10-19: {count}")

if count > 0:
    cursor.execute("SELECT ticker, performance FROM stock_performance WHERE date = '2025-10-19' ORDER BY performance DESC LIMIT 3")
    print("   Top 3 performers:")
    for row in cursor.fetchall():
        print(f"     {row['ticker']}: {row['performance']}%")

conn.close()

print("\n" + "="*70 + "\n")
