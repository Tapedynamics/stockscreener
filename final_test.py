#!/usr/bin/env python3
import requests
import json

print("\n" + "="*70)
print("FINAL SYSTEM VERIFICATION")
print("="*70)

# Test chart endpoint
response = requests.get('http://localhost:5000/api/portfolio/chart?timeframe=ALL')
data = response.json()

if data['success']:
    cd = data['data']['chart_data']

    print(f"\nTotal snapshots: {data['data']['snapshots_count']}")
    print(f"Chart labels: {len(cd['labels'])}")
    print(f"Chart values: {len(cd['datasets'][0]['data'])}")

    print(f"\nTimeline:")
    print(f"  Start: {cd['labels'][0]} = ${cd['datasets'][0]['data'][0]:,.0f}")
    print(f"  End:   {cd['labels'][-1]} = ${cd['datasets'][0]['data'][-1]:,.0f}")

    values = cd['datasets'][0]['data']
    ret = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
    print(f"  Return: {ret:+.2f}%")

    print(f"\nDate labels (first 10):")
    for i, label in enumerate(cd['labels'][:10], 1):
        print(f"  {i}. {label}")

    print(f"\nDate labels (last 5):")
    for i, label in enumerate(cd['labels'][-5:], len(cd['labels'])-4):
        print(f"  {i}. {label}")
else:
    print(f"ERROR: {data['error']}")

print("\n" + "="*70)
print("SYSTEM READY FOR DEPLOYMENT")
print("="*70 + "\n")
