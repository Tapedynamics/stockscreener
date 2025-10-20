#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()

# Check table structure
print("Table structure:")
cursor.execute("PRAGMA table_info(portfolio_snapshots);")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col}")

# Check is_locked values
print("\nChecking is_locked values:")
cursor.execute("SELECT id, timestamp, is_locked FROM portfolio_snapshots LIMIT 5;")
rows = cursor.fetchall()
for row in rows:
    print(f"  ID: {row[0]}, Timestamp: {row[1]}, is_locked: {row[2]}")

# Count by is_locked
print("\nCount by is_locked value:")
cursor.execute("SELECT is_locked, COUNT(*) FROM portfolio_snapshots GROUP BY is_locked;")
counts = cursor.fetchall()
for count in counts:
    print(f"  is_locked={count[0]}: {count[1]} snapshots")

# Try to update
print("\nTrying to update all to locked=1...")
cursor.execute("UPDATE portfolio_snapshots SET is_locked = 1;")
conn.commit()
print(f"  Updated {cursor.rowcount} rows")

# Recheck
cursor.execute("SELECT is_locked, COUNT(*) FROM portfolio_snapshots GROUP BY is_locked;")
counts = cursor.fetchall()
print("\nAfter update:")
for count in counts:
    print(f"  is_locked={count[0]}: {count[1]} snapshots")

conn.close()
