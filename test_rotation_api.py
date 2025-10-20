#!/usr/bin/env python3
"""
Quick test of rotation API endpoints
"""

import requests
import json

BASE_URL = "http://localhost:5000"

print("\n" + "="*70)
print("TESTING MOMENTUM ROTATION API ENDPOINTS")
print("="*70)

# Test 1: Get cooldown stocks
print("\n1. Testing /api/rotation/cooldown...")
try:
    response = requests.get(f"{BASE_URL}/api/rotation/cooldown")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data.get('success'):
        cooldowns = data['data']['cooldowns']
        print(f"   Stocks in cooldown: {data['data']['total']}")
        for c in cooldowns[:3]:
            print(f"     - {c['ticker']}: {c['days_remaining']} days remaining")
    else:
        print(f"   Error: {data.get('error')}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 2: Get momentum rankings
print("\n2. Testing /api/rotation/rankings...")
try:
    response = requests.get(f"{BASE_URL}/api/rotation/rankings")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data.get('success'):
        rankings = data['data']['rankings']
        print(f"   Total ranked: {data['data']['total']}")
        print("   Top 5:")
        for r in rankings[:5]:
            print(f"     #{r['rank']} {r['ticker']}: {r['performance']:+.2f}%")
    else:
        print(f"   Error: {data.get('error')}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 3: Get rotation suggestions
print("\n3. Testing /api/rotation/suggest...")
try:
    response = requests.get(f"{BASE_URL}/api/rotation/suggest")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data.get('success'):
        suggestions = data['data']
        print(f"   Total sells: {suggestions['total_sells']}")
        print(f"   Total buys: {suggestions['total_buys']}")
        print(f"   Slots to fill: {suggestions['slots_to_fill']}")

        if suggestions['to_sell']:
            print("\n   Sell suggestions:")
            for sell in suggestions['to_sell']:
                print(f"     - {sell['ticker']} (reason: {sell['reason']}, rank: #{sell['rank']})")

        if suggestions['to_buy']:
            print("\n   Buy suggestions:")
            for buy in suggestions['to_buy'][:5]:
                print(f"     - {buy['ticker']} (rank: #{buy['rank']}, perf: {buy['performance']:+.2f}%)")
    else:
        print(f"   Error: {data.get('error')}")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "="*70)
print("TESTS COMPLETE")
print("="*70 + "\n")
