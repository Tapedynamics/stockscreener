#!/usr/bin/env python3
"""
Export all data from Render production database
Saves to JSON file for later import to PostgreSQL
"""

import requests
import json
from datetime import datetime

RENDER_URL = "https://stockscreener-2aeg.onrender.com"

def export_all_data():
    """Export all data via API endpoints"""
    print("=" * 60)
    print("EXPORTING DATA FROM RENDER")
    print("=" * 60)
    print()

    exported_data = {
        'export_date': datetime.now().isoformat(),
        'trades': [],
        'portfolio_snapshots': [],
        'activity_log': []
    }

    # Export trades
    print("1. Exporting trades...")
    try:
        response = requests.get(f"{RENDER_URL}/api/trades?limit=1000")
        data = response.json()
        if data['success']:
            exported_data['trades'] = data['data']['trades']
            print(f"   [OK] Exported {len(exported_data['trades'])} trades")
        else:
            print(f"   [ERROR] {data.get('error')}")
    except Exception as e:
        print(f"   [ERROR] {e}")

    # Export portfolio snapshots
    print("2. Exporting portfolio snapshots...")
    try:
        response = requests.get(f"{RENDER_URL}/api/portfolio/history?limit=1000")
        data = response.json()
        if data['success']:
            exported_data['portfolio_snapshots'] = data['data']
            print(f"   [OK] Exported {len(exported_data['portfolio_snapshots'])} snapshots")
        else:
            print(f"   [ERROR] {data.get('error')}")
    except Exception as e:
        print(f"   [ERROR] {e}")

    # Export activity log
    print("3. Exporting activity log...")
    try:
        response = requests.get(f"{RENDER_URL}/api/activity-log")
        data = response.json()
        if data['success']:
            exported_data['activity_log'] = data['data']
            print(f"   [OK] Exported {len(exported_data['activity_log'])} log entries")
        else:
            print(f"   [ERROR] {data.get('error')}")
    except Exception as e:
        print(f"   [ERROR] {e}")

    # Save to file
    filename = f"render_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(exported_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"[SUCCESS] DATA EXPORTED TO: {filename}")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  - Trades: {len(exported_data['trades'])}")
    print(f"  - Snapshots: {len(exported_data['portfolio_snapshots'])}")
    print(f"  - Activity Log: {len(exported_data['activity_log'])}")
    print()

    return filename

if __name__ == "__main__":
    export_all_data()
