#!/usr/bin/env python3
"""
Save baseline YTD 2025 performance to database
This becomes the reference point for all future comparisons
"""

from database import get_db
from datetime import datetime

# Real performance data from YTD 2025 calculation
# Same 15 tickers from 2024 baseline for comparison
BASELINE_DATA = {
    'calculation_date': '2025-10-19',
    'period_start': '2025-01-01',
    'period_end': '2025-10-19',
    'initial_investment': 150000.00,
    'final_value': 210828.38,
    'total_gain': 60828.38,
    'total_return_pct': 40.55,
    'num_stocks': 15,
    'tickers': ['NXT', 'JBHT', 'SCCO', 'MU', 'NEE', 'AMAT', 'CXT', 'CAT',
                'AES', 'XEL', 'ELAN', 'SR', 'ESAB', 'TXRH', 'JNJ'],
    'individual_returns': {
        'NXT': 120.41,
        'JBHT': -2.84,
        'SCCO': 46.92,
        'MU': 132.41,
        'NEE': 20.91,
        'AMAT': 38.40,
        'CXT': 15.07,
        'CAT': 48.29,
        'AES': 17.10,
        'XEL': 25.42,
        'ELAN': 77.76,
        'SR': 28.75,
        'ESAB': 3.24,
        'TXRH': -0.93,
        'JNJ': 37.40
    },
    'best_performer': ('MU', 132.41),
    'worst_performer': ('JBHT', -2.84)
}

def save_baseline_performance():
    """Save baseline performance data to database"""
    db = get_db()

    print("\n" + "="*70)
    print("SAVING BASELINE YTD 2025 PERFORMANCE TO DATABASE")
    print("="*70)
    print(f"\nPeriod: {BASELINE_DATA['period_start']} to {BASELINE_DATA['period_end']}")
    print(f"Total Return: +{BASELINE_DATA['total_return_pct']:.2f}%")
    print(f"Portfolio Value: ${BASELINE_DATA['final_value']:,.2f}")
    print("="*70 + "\n")

    # 1. Save aggregate portfolio performance to settings
    print("1. Saving portfolio aggregate data to settings...")
    db.set_setting('baseline_ytd_2025_return', str(BASELINE_DATA['total_return_pct']))
    db.set_setting('baseline_ytd_2025_value', str(BASELINE_DATA['final_value']))
    db.set_setting('baseline_ytd_2025_gain', str(BASELINE_DATA['total_gain']))
    db.set_setting('baseline_ytd_2025_period_start', BASELINE_DATA['period_start'])
    db.set_setting('baseline_ytd_2025_period_end', BASELINE_DATA['period_end'])
    db.set_setting('baseline_ytd_2025_best_stock', f"{BASELINE_DATA['best_performer'][0]}:{BASELINE_DATA['best_performer'][1]}")
    db.set_setting('baseline_ytd_2025_worst_stock', f"{BASELINE_DATA['worst_performer'][0]}:{BASELINE_DATA['worst_performer'][1]}")
    print("   [OK] Portfolio data saved to settings")

    # 2. Save individual stock performance
    print("\n2. Saving individual stock performance...")
    conn = db.get_connection()
    cursor = conn.cursor()

    date_str = BASELINE_DATA['calculation_date']

    for ticker, return_pct in BASELINE_DATA['individual_returns'].items():
        cursor.execute('''
            INSERT OR REPLACE INTO stock_performance
            (ticker, date, price, performance)
            VALUES (?, ?, NULL, ?)
        ''', (ticker, date_str, return_pct))

    conn.commit()
    conn.close()
    print(f"   [OK] Saved performance for {len(BASELINE_DATA['individual_returns'])} stocks")

    # 3. Create a baseline snapshot for reference
    print("\n3. Creating baseline reference snapshot...")
    snapshot_id = db.save_portfolio_snapshot(
        take_profit=['NXT', 'JBHT', 'SCCO'],
        hold=['MU', 'NEE', 'AMAT', 'CXT', 'CAT', 'AES', 'XEL', 'ELAN', 'SR', 'ESAB'],
        buffer=['TXRH', 'JNJ'],
        notes=f'BASELINE YTD 2025: Real performance +{BASELINE_DATA["total_return_pct"]:.2f}% (Jan-Oct 2025) - Same tickers as 2024',
        portfolio_value=BASELINE_DATA['final_value']
    )
    print(f"   [OK] Baseline snapshot created (ID: {snapshot_id})")

    # 4. Save metadata
    print("\n4. Saving metadata...")
    db.set_setting('baseline_snapshot_id', str(snapshot_id))
    db.set_setting('baseline_calculation_date', BASELINE_DATA['calculation_date'])
    print("   [OK] Metadata saved")

    print("\n" + "="*70)
    print("BASELINE DATA SAVED SUCCESSFULLY")
    print("="*70)
    print("\nThis baseline will be used for:")
    print("  - Comparing future portfolio performance")
    print("  - Calculating relative returns")
    print("  - Benchmark analysis")
    print("\nTo view baseline data:")
    print("  - Check /api/settings for baseline_ytd_2025_* values")
    print("  - View stock_performance table for individual returns")
    print("  - See baseline snapshot in portfolio history")
    print("="*70 + "\n")

    return snapshot_id

if __name__ == '__main__':
    try:
        snapshot_id = save_baseline_performance()
        print(f"[SUCCESS] Baseline saved with snapshot ID: {snapshot_id}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
