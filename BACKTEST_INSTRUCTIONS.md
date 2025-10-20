# Accurate Finviz Strategy Backtest Instructions

## Problem Identified

When backtesting with the current Finviz universe (October 2025) for January 2025 data, we discovered **look-ahead bias**:

- Only **5 out of 20** current stocks (25%) would have passed Finviz filters in January
- 15 stocks failed because they were **below SMA 200** in January
- Using current universe creates artificially inflated backtest results

**Stocks that PASSED in January 2025:**
- NXT, MU, AMAT, CXT, EME

**Stocks that FAILED in January 2025:**
- JBHT, SCCO, NEE, CAT, AES, XEL, ELAN, SR, ESAB, TXRH, JNJ, WTRG, SRE, AEP, CSX

## Solution

To run an accurate backtest, we need the **actual universe of stocks that passed ALL Finviz filters in January 2025**.

### Finviz Filters (11 criteria):

1. **Market Cap**: $2B+ (mid-cap and above)
2. **EPS 5Y Growth**: Positive
3. **Est. Long-Term Growth**: Positive
4. **Net Margin**: Positive
5. **Operating Margin**: Positive
6. **ROE**: Positive
7. **P/E Ratio**: Under 30
8. **Country**: USA only
9. **Avg Volume**: > 100K shares
10. **Current Volume**: > 100K shares
11. **Price vs SMA 200**: Above

**Sorting**: By 4-week performance (descending)

## Step-by-Step Instructions

### Step 1: Get FMP API Key (2 minutes)

Financial Modeling Prep (FMP) provides historical fundamental data for free:

1. Go to: https://financialmodelingprep.com/developer/docs/
2. Click **"Get my API KEY here"**
3. Sign up (free account)
4. Copy your API key
5. Add to `.env` file:
   ```
   FMP_API_KEY=your_key_here
   ```

**Free tier limits:**
- 250 API calls per day
- Historical fundamental data included
- No credit card required

### Step 2: Verify January 2025 Universe

Run the verification script:

```bash
python verify_january_universe_with_fmp.py
```

**What it does:**
1. Builds starting universe (S&P 500 + common mid/large caps ~600 stocks)
2. Downloads historical price/volume data from Yahoo Finance
3. Filters by **technical criteria** (price, volume, SMA 200) for January 6, 2025
4. Queries FMP API for **historical fundamentals** (2024 annual reports)
5. Applies ALL 11 Finviz filters
6. Saves verified universe to `january_2025_universe.txt`

**Expected output:**
```
Stocks that passed ALL filters in January 2025:
  Count: 15-25 (estimate)
  Tickers: [list of verified stocks]

Results saved to: january_2025_universe.txt
```

**API Usage:**
- ~50-100 stocks pass technical filters
- 4 API calls per stock (metrics, ratios, income, growth)
- Total: ~200-400 API calls
- May need to run over 2 days if exceeding 250/day limit

### Step 3: Run Accurate Backtest

Once you have `january_2025_universe.txt`:

```bash
python backtest_finviz_strategy.py
```

The script will:
1. Detect the January universe file
2. Ask which universe to use:
   - **Option 1**: January 2025 verified universe (RECOMMENDED)
   - **Option 2**: Current Finviz universe (has look-ahead bias)
3. Run backtest with weekly momentum rotation
4. Apply 15% trailing stop
5. Generate 41 weeks of historical snapshots
6. Lock all snapshots as historical data

**Backtest configuration:**
- **Period**: January 6 - October 13, 2025 (41 weeks)
- **Initial Capital**: $150,000
- **Portfolio Size**: 12 stocks
- **Trailing Stop**: 15% from peak
- **Rebalancing**: Weekly (Mondays)
- **Momentum**: 4-week (30-day) performance ranking

### Step 4: Review Results

After backtest completes:

1. **Check console output:**
   - Total return
   - Average weekly return
   - Number of trades
   - Stop loss trigger rate

2. **View in web interface:**
   ```bash
   python app.py
   ```
   - Go to **History** tab → See 41 weekly snapshots
   - Go to **Chart** tab → See equity curve
   - All snapshots are **locked** (protected from modification)

3. **Verify data integrity:**
   ```bash
   python check_equity_linearity.py
   ```
   - Confirms no anomalies in equity curve
   - Checks for unrealistic weekly returns

## Alternative: Quick Test Without FMP API

If you want to test the backtest logic without getting an API key:

```bash
# Use current universe (has look-ahead bias but tests the logic)
python backtest_finviz_strategy.py

# When prompted, choose Option 2 (Current Finviz universe)
```

⚠️ **Warning**: Results will be artificially inflated due to look-ahead bias. Only use for testing the backtest logic.

## Files Created

1. **verify_january_universe_with_fmp.py** - Verifies January universe with FMP API
2. **january_2025_universe.txt** - Verified universe (created after Step 2)
3. **backtest_finviz_strategy.py** - Updated to support both universes
4. **BACKTEST_INSTRUCTIONS.md** - This file

## Troubleshooting

### "FMP API KEY REQUIRED"
- Make sure you added `FMP_API_KEY=your_key` to `.env` file
- Or enter it when prompted

### "ERROR: 429 Too Many Requests"
- Free tier limit exceeded (250 calls/day)
- Wait 24 hours and re-run
- Script will resume from where it stopped

### "No fundamental data available"
- Some stocks may lack historical financials on FMP
- This is normal - they'll be filtered out
- Final universe will include only stocks with complete data

### "Results differ from expected"
- Verify `january_2025_universe.txt` contains correct stocks
- Check console output for API errors
- Ensure Yahoo Finance data downloaded successfully

## Expected Performance

Based on preliminary analysis:

- **Universe Size**: 15-25 stocks (depending on how many pass all filters)
- **Typical Turnover**: 30-60% weekly (momentum strategy is dynamic)
- **Stop Loss Triggers**: 15-30% of all sells
- **Expected Return**: TBD (depends on actual January universe)

## Why This Matters

**Without proper universe:**
- Backtest uses stocks that weren't actually available
- Creates survivorship bias (only stocks that survived to October)
- Results are artificially inflated
- Strategy appears better than reality

**With verified universe:**
- Uses only stocks that actually passed filters in January
- Realistic simulation of strategy performance
- Accurate measurement of drawdowns and returns
- Confidence in strategy viability

## Next Steps After Backtest

1. **Analyze Results**:
   - Compare to S&P 500 benchmark
   - Review maximum drawdown
   - Check Sharpe ratio
   - Analyze stop loss effectiveness

2. **Optimize Parameters**:
   - Test different portfolio sizes (10, 12, 15)
   - Adjust trailing stop (10%, 15%, 20%)
   - Vary rebalancing frequency (weekly, bi-weekly)

3. **Forward Testing**:
   - Continue with live Finviz screening
   - Track real-time performance vs backtest
   - Adjust strategy based on results

---

**Questions?** Check the code comments in `verify_january_universe_with_fmp.py` and `backtest_finviz_strategy.py` for detailed explanations.
