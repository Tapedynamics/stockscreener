#!/usr/bin/env python3
"""
Clean all simulated historical data from database
Keep only baseline snapshots
"""

from database import get_db

db = get_db()
conn = db.get_connection()
cursor = conn.cursor()

print("\n" + "="*70)
print("DATABASE CLEANUP - Remove Simulated Data")
print("="*70)

# Count current data
cursor.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
total_snapshots = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM activity_log")
total_logs = cursor.fetchone()['count']

print(f"\nCurrent database state:")
print(f"  Portfolio snapshots: {total_snapshots}")
print(f"  Activity log entries: {total_logs}")

# Show baseline snapshots (we want to keep these)
print(f"\nBaseline snapshots to KEEP:")
cursor.execute("SELECT id, timestamp, notes FROM portfolio_snapshots WHERE notes LIKE '%BASELINE%' ORDER BY id")
baselines = cursor.fetchall()
baseline_ids = []
for row in baselines:
    print(f"  ID {row['id']}: {row['notes']}")
    baseline_ids.append(row['id'])

# Ask for confirmation
print(f"\n" + "="*70)
print("WARNING: This will delete ALL portfolio snapshots and activity logs")
print(f"EXCEPT baseline snapshots (IDs: {baseline_ids})")
print("="*70)

response = input("\nProceed with deletion? (yes/no): ")

if response.lower() == 'yes':
    # Delete activity log
    cursor.execute("DELETE FROM activity_log")
    deleted_logs = cursor.rowcount

    # Delete non-baseline snapshots
    if baseline_ids:
        placeholders = ','.join('?' * len(baseline_ids))
        cursor.execute(f"DELETE FROM portfolio_snapshots WHERE id NOT IN ({placeholders})", baseline_ids)
    else:
        cursor.execute("DELETE FROM portfolio_snapshots")
    deleted_snapshots = cursor.rowcount

    conn.commit()

    print(f"\n[OK] Deleted {deleted_snapshots} portfolio snapshots")
    print(f"[OK] Deleted {deleted_logs} activity log entries")
    print(f"[OK] Kept {len(baseline_ids)} baseline snapshots")

    # Show remaining data
    cursor.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
    remaining = cursor.fetchone()['count']
    print(f"\nRemaining portfolio snapshots: {remaining}")

    print("\n" + "="*70)
    print("CLEANUP COMPLETE")
    print("="*70 + "\n")
else:
    print("\nCancelled - no changes made\n")

conn.close()
