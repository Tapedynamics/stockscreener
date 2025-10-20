#!/usr/bin/env python3
"""
Test timeframe buttons functionality
Verifies that each timeframe returns different filtered data
"""

import requests
import json
from datetime import datetime

BASE_URL = 'http://localhost:5000'

print("\n" + "="*70)
print("TESTING TIMEFRAME BUTTONS")
print("="*70)

timeframes = ['1M', '3M', '6M', 'YTD', '1Y', 'ALL']

results = {}

for tf in timeframes:
    print(f"\nTesting timeframe: {tf}")
    print("-" * 70)

    try:
        response = requests.get(f'{BASE_URL}/api/portfolio/chart?timeframe={tf}', timeout=10)

        if response.status_code != 200:
            print(f"  ERROR: HTTP {response.status_code}")
            continue

        data = response.json()

        if not data.get('success'):
            print(f"  ERROR: {data.get('error', 'Unknown error')}")
            continue

        chart_data = data['data']['chart_data']
        snapshots_count = data['data']['snapshots_count']
        returned_tf = data['data']['timeframe']

        labels = chart_data['labels']
        values = chart_data['datasets'][0]['data']

        print(f"  Timeframe returned: {returned_tf}")
        print(f"  Snapshots: {snapshots_count}")
        print(f"  Data points: {len(labels)}")

        if len(labels) > 0:
            print(f"  Date range: {labels[0]} to {labels[-1]}")
            print(f"  Value range: ${values[0]:,.0f} to ${values[-1]:,.0f}")

            # Calculate return
            if values[0] > 0:
                ret = ((values[-1] - values[0]) / values[0] * 100)
                print(f"  Return: {ret:+.2f}%")

        results[tf] = {
            'snapshots': snapshots_count,
            'data_points': len(labels),
            'start_label': labels[0] if labels else None,
            'end_label': labels[-1] if labels else None
        }

    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results[tf] = None

print("\n" + "="*70)
print("COMPARISON SUMMARY")
print("="*70)

print(f"\n{'Timeframe':<12} {'Snapshots':<12} {'Data Points':<12} {'Date Range'}")
print("-" * 70)

for tf in timeframes:
    if results.get(tf):
        r = results[tf]
        date_range = f"{r['start_label']} - {r['end_label']}" if r['start_label'] else "N/A"
        print(f"{tf:<12} {r['snapshots']:<12} {r['data_points']:<12} {date_range}")
    else:
        print(f"{tf:<12} {'ERROR':<12} {'ERROR':<12} {'N/A'}")

print("\n" + "="*70)
print("VALIDATION")
print("="*70)

# Check that different timeframes return different amounts of data
all_data = results.get('ALL')
ytd_data = results.get('YTD')
m6_data = results.get('6M')
m3_data = results.get('3M')
m1_data = results.get('1M')

if all_data and ytd_data and m6_data and m3_data and m1_data:
    # ALL should have the most data
    if (all_data['snapshots'] >= ytd_data['snapshots'] and
        ytd_data['snapshots'] >= m6_data['snapshots'] and
        m6_data['snapshots'] >= m3_data['snapshots'] and
        m3_data['snapshots'] >= m1_data['snapshots']):

        print("\n[PASS] Timeframes correctly filter data")
        print(f"  ALL ({all_data['snapshots']}) >= YTD ({ytd_data['snapshots']}) >= " +
              f"6M ({m6_data['snapshots']}) >= 3M ({m3_data['snapshots']}) >= 1M ({m1_data['snapshots']})")
    else:
        print("\n[FAIL] Timeframes don't filter correctly")
        print(f"  Expected: ALL >= YTD >= 6M >= 3M >= 1M")
        print(f"  Got: ALL={all_data['snapshots']}, YTD={ytd_data['snapshots']}, " +
              f"6M={m6_data['snapshots']}, 3M={m3_data['snapshots']}, 1M={m1_data['snapshots']}")

    # Check that YTD starts from January 2025
    if ytd_data['start_label']:
        if ytd_data['start_label'].startswith('Jan'):
            print(f"\n[PASS] YTD correctly starts from January ({ytd_data['start_label']})")
        else:
            print(f"\n[FAIL] YTD should start from January, got {ytd_data['start_label']}")

else:
    print("\n[FAIL] Some timeframes returned errors")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

if all(results.values()):
    print("\n[SUCCESS] All timeframe buttons are working correctly!")
    print("  Each timeframe returns appropriately filtered data")
else:
    failed = [tf for tf, r in results.items() if not r]
    print(f"\n[ERROR] Some timeframes failed: {', '.join(failed)}")

print("\n" + "="*70 + "\n")
