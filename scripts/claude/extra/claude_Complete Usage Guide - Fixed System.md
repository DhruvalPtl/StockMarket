# 🚀 Complete Nifty Algo Trading System - Usage Guide

## 📦 What's Included

### 1. **Fixed Data Pipeline** (`fixed_data_pipeline.py`)
- ✅ OI change tracking
- ✅ All Greeks (Delta, Gamma, Theta, Vega, IV)
- ✅ Total CE/PE OI calculation
- ✅ Rate limiting
- ✅ Real-time status display

### 2. **Fixed Advanced Recorder** (`fixed_advanced_recorder.py`)
- ✅ Optimized strike range (±2000 points from spot = ~50 strikes instead of 236)
- ✅ OI change tracking
- ✅ All Greeks included
- ✅ 3 separate CSV files (Spot, Options, Chain)

### 3. **CSV Backtester** (`csv_backtester.py`)
- ✅ Test strategies on recorded data
- ✅ Custom strategy functions
- ✅ Detailed performance metrics
- ✅ Export results

### 4. **API Backtester** (`api_backtester.py`)
- ✅ Fetch historical data directly from Groww
- ✅ Test without recording first
- ✅ Same strategy interface as CSV version

---

## 🔧 Installation

### 1. Replace Your Files
```bash
# Backup your old files first
mv groww_data_pipeline.py groww_data_pipeline.py.old
mv claude_advanced_market_recorder.py claude_advanced_market_recorder.py.old

# Copy new fixed versions
cp fixed_data_pipeline.py groww_data_pipeline.py
cp fixed_advanced_recorder.py claude_advanced_market_recorder.py
```

### 2. Install Required Packages
```bash
pip install pandas numpy growwapi
```

---

## 📊 Recording Data

### Option A: Advanced Recorder (Recommended)
```python
python fixed_advanced_recorder.py
```

**What it records:**
- **Spot_Data_YYYY-MM-DD.csv**: Index prices + indicators
- **Options_Data_YYYY-MM-DD.csv**: ATM options with ALL Greeks
- **Optimized_Chain_YYYY-MM-DD.csv**: Only relevant strikes (±2000 from spot)

**Key Features:**
- Records ~50 strikes instead of 236 (80% less data)
- All OI changes tracked
- All Greeks included
- Rate limiting built-in

### Option B: Just Use Data Pipeline
The fixed data pipeline is already integrated into your bot. It will automatically:
- Track OI changes
- Include all Greeks
- Calculate total OI
- Handle rate limiting

---

## 🧪 Backtesting

### Method 1: CSV-Based (Faster, No API Calls)

```python
from csv_backtester import CSVBacktester, momentum_burst_strategy

# Load your recorded data
backtester = CSVBacktester("Master_Data_2025-12-24.csv", initial_capital=10000)

# Run backtest
backtester.run(momentum_burst_strategy)
```

**Advantages:**
- ✅ Very fast (no API calls)
- ✅ Test on real recorded market data
- ✅ Unlimited iterations
- ✅ No rate limits

### Method 2: API-Based (Fresh Data)

```python
from api_backtester import APIBacktester

# Initialize
backtester = APIBacktester(
    api_key="YOUR_KEY",
    api_secret="YOUR_SECRET",
    start_date="2025-12-24 09:15:00",
    end_date="2025-12-24 15:30:00",
    expiry_date="2025-12-30",
    initial_capital=10000
)

# Fetch and test
if backtester.fetch_historical_data(interval="5minute"):
    backtester.run(momentum_burst_strategy)
```

**Advantages:**
- ✅ Don't need to record first
- ✅ Can test any date range
- ✅ Always fresh from API

**Disadvantages:**
- ⚠️ Slower (fetches from API)
- ⚠️ Subject to rate limits
- ⚠️ Uses API quota

---

## 🎯 Creating Custom Strategies

### Basic Template
```python
def my_strategy(row, engine_state):
    """
    Your strategy logic here
    
    Args:
        row: Pandas row from CSV
        engine_state: Dict with keys:
            - spot, rsi, vwap, ema5, ema13
            - pcr, atm_strike
            - ce_price, pe_price
            - ce_oi, pe_oi
    
    Returns:
        'BUY_CE', 'BUY_PE', or None
    """
    
    # Example: Buy PE when oversold
    if engine_state['rsi'] < 35 and engine_state['spot'] < engine_state['vwap']:
        return 'BUY_PE'
    
    # Example: Buy CE when overbought
    if engine_state['rsi'] > 65 and engine_state['spot'] > engine_state['vwap']:
        return 'BUY_CE'
    
    return None
```

### Advanced Example (Your Current Strategy)
```python
def momentum_burst_strategy(row, engine_state):
    """
    High win-rate scalping strategy
    - Oversold bounce for PE
    - Overbought momentum for CE
    """
    rsi = engine_state['rsi']
    spot = engine_state['spot']
    vwap = engine_state['vwap']
    pcr = engine_state['pcr']
    
    # Strong bearish (buy PE)
    if rsi < 40 and spot < vwap and 0.85 < pcr < 0.95:
        return 'BUY_PE'
    
    # Strong bullish (buy CE)
    if rsi > 55 and spot > vwap and pcr > 1.05:
        return 'BUY_CE'
    
    return None
```

---

## 📈 Understanding the Results

### Backtest Output
```
📊 BACKTEST RESULTS
======================================================================
Initial Capital: Rs.10,000.00
Final Capital:   Rs.10,521.25
Total PnL:       Rs.521.25 (5.21%)

Total Trades:    10
Winning Trades:  7
Losing Trades:   3
Win Rate:        70.0%

Average Win:     Rs.250.00
Max Win:         Rs.761.25
Average Loss:    Rs.-402.50
Max Loss:        Rs.-1,200.00

Exit Reasons:
  TARGET: 5
  STOP_LOSS: 3
  TIME_EXIT: 2
```

### Key Metrics to Watch

**Win Rate**: Should be > 60% for scalping strategies
- Your current: **75%** ✅

**Risk-Reward**: Average Win / Average Loss
- Your current: 250 / 402.5 = 0.62 ⚠️
- Target: > 1.0 (improve by tightening stops or wider targets)

**Max Drawdown**: Largest losing trade
- Your current: -1200 (12% of capital) ⚠️
- Target: < 10% of capital

---

## 🔍 What's Fixed in New Version

### 1. OI Change Tracking ✅
**Before:**
```
CE_OI_Chg    PE_OI_Chg
0            0          <- Always zero!
```

**After:**
```
CE_OI_Chg    PE_OI_Chg
-4644        -6846      <- Real changes!
```

### 2. Strike Range Optimization ✅
**Before:**
- Recording 236 strikes (13000 to 31000)
- 95% had 0 volume/OI
- Wasted API calls

**After:**
- Recording ~50 strikes (24150 to 28150)
- All strikes have active trading
- 80% fewer API calls

### 3. All Greeks Included ✅
**Before:**
```
Gamma  Vega  IV
0      0     0
```

**After:**
```
Gamma      Vega   IV
0.001523   13.45  24.5
```

### 4. Total OI Calculation ✅
**Before:**
```
Total_CE_OI  Total_PE_OI
0            0
```

**After:**
```
Total_CE_OI    Total_PE_OI
8,234,567      9,876,543
```

---

## 🎓 Workflow Recommendations

### For Development (Testing Strategies)
1. **Record 1 full day** using Fixed Advanced Recorder
2. **Test multiple strategies** using CSV Backtester (fast, unlimited)
3. **Optimize parameters** (RSI levels, targets, stops)
4. **Validate** on different days using API Backtester

### For Live Trading
1. Use the fixed data pipeline (already in your bot)
2. Bot automatically has OI tracking + all Greeks
3. Monitor real-time for patterns
4. Let bot execute with paper trading first

---

## 📞 Support

### Common Issues

**Q: Rate limit errors?**
A: Fixed pipeline adds delays between API calls. If still seeing errors, increase `min_delay` values in `_rate_limit()` method.

**Q: OI changes still showing 0?**
A: Make sure you're using the NEW fixed pipeline. Old one doesn't track OI.

**Q: Backtest shows no trades?**
A: Your strategy might be too strict. Try relaxing conditions (e.g., RSI < 40 instead of < 35).

**Q: How to test on multiple days?**
A: Use API Backtester with different date ranges:
```python
# Test week 1
backtester = APIBacktester(..., "2025-12-16 09:15:00", "2025-12-16 15:30:00", ...)

# Test week 2
backtester = APIBacktester(..., "2025-12-23 09:15:00", "2025-12-23 15:30:00", ...)
```

---

## 🚀 Next Steps

1. **Test the fixed recorder** for one session
2. **Run CSV backtest** on your recorded data
3. **Optimize your strategy** based on results
4. **Validate with API backtest** on different dates
5. **Paper trade with live bot** before using real money

---

## ⚠️ Important Notes

- Always **paper trade** before real money
- Fixed system uses **rate limiting** to avoid API blocks
- **OI changes** are now tracked properly for pattern detection
- **Strike range** optimized to save 80% of API calls
- All **Greeks** now included for advanced strategies

**Good luck! 🎯**
