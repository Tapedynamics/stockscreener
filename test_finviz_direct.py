#!/usr/bin/env python3
"""
Test direct Finviz response
"""

from stock_screener import get_finviz_stocks

FINVIZ_URL = "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"

print("\n" + "="*70)
print("TESTING DIRECT FINVIZ RESPONSE")
print("="*70)
print(f"\nURL: {FINVIZ_URL}")
print("\nParameters decoded:")
print("  - cap_midover: Mid cap and OVER (excludes small cap)")
print("  - fa_pe_u30: P/E under 30")
print("  - ta_sma200_pa: Price above SMA 200")
print("  - o=-perf4w: Sorted by 4-week performance (descending)")

print("\nFetching from Finviz...")

try:
    stocks = get_finviz_stocks(FINVIZ_URL)

    print(f"\nTotal stocks found: {len(stocks)}")
    print(f"\nFirst 20 tickers:")
    for i, ticker in enumerate(stocks[:20], 1):
        print(f"  {i:2d}. {ticker}")

    print("\n" + "="*70)

    # Check if these are big/mid cap
    import yfinance as yf
    print("\nChecking market cap for first 5...")
    for ticker in stocks[:5]:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mcap = info.get('marketCap', 0)
            if mcap > 0:
                mcap_b = mcap / 1e9
                if mcap_b > 10:
                    cap_size = "Large cap"
                elif mcap_b > 2:
                    cap_size = "Mid cap"
                else:
                    cap_size = "Small cap"
                print(f"  {ticker}: ${mcap_b:.2f}B ({cap_size})")
            else:
                print(f"  {ticker}: Market cap not available")
        except Exception as e:
            print(f"  {ticker}: Error - {e}")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")
