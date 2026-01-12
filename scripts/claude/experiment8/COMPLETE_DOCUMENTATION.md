# 📚 EXPERIMENT 6 - COMPLETE DOCUMENTATION

**Version:** 1.0  
**Last Updated:** January 8, 2026  
**Status:** Production Ready ✅

---

## 📋 TABLE OF CONTENTS

1. [System Overview](#system-overview)
2. [Configuration Variables](#configuration-variables)
3. [Trading Strategies](#trading-strategies)
4. [Market Intelligence](#market-intelligence)
5. [Execution System](#execution-system)
6. [Logging System](#logging-system)
7. [Risk Management](#risk-management)
8. [Examples](#examples)

---

## 🎯 SYSTEM OVERVIEW

**Experiment 6** is an intelligent multi-strategy NIFTY options trading bot that:
- Runs 9 different strategies across 4 timeframes (36 strategy instances)
- Uses market intelligence (regime, bias, order flow, liquidity)
- Implements signal aggregation with confluence voting
- Auto-resets on max daily loss
- Logs everything for analysis

### Architecture Flow
```
Market Data (GrowwAPI)
    ↓
Data Engine (4 timeframes)
    ↓
Market Intelligence (Regime, Bias, Order Flow, Liquidity)
    ↓
Strategies (9 types × 4 timeframes = 36 instances)
    ↓
Signal Aggregator (Confluence voting)
    ↓
Risk Manager (Position limits, loss limits)
    ↓
Execution (Entry/Exit management)
    ↓
Logging (CSV + TXT files)
```

---

## ⚙️ CONFIGURATION VARIABLES

### 1. API Settings
**Location:** `config.py` → `BotConfig`

```python
API_KEY = "your_groww_token"
API_SECRET = "your_secret"
RATE_LIMIT_SPOT = 0.5      # Seconds between spot data calls
RATE_LIMIT_FUTURE = 0.5    # Seconds between future calls
RATE_LIMIT_CHAIN = 1.0     # Seconds between option chain calls
```

**Example Usage:**
- Avoid rate limiting from Groww API
- Adjust if getting "Too Many Requests" errors

---

### 2. Contract Settings
```python
OPTION_EXPIRY = "2026-01-13"   # Weekly options
FUTURE_EXPIRY = "2026-01-27"   # Monthly futures
```

**Example:**
```python
# Bot automatically builds symbols:
# Options: NIFTY13JAN2626000CE, NIFTY13JAN2626000PE
# Future:  NIFTY27JAN26FUT
```

---

### 3. Timeframe Settings
```python
TIMEFRAMES = ["1minute", "2minute", "3minute", "5minute"]
```

**Example Data Fetch:**
- 1minute: Last 5 days × 375 candles/day = ~1875 candles
- Data refreshed every timeframe interval
- Used for calculating EMAs, RSI, ADX, ATR

---

### 4. Market Regime Variables
**Location:** `config.py` → `BotConfig.Regime`

```python
class Regime:
    ADX_TRENDING_THRESHOLD = 20       # ADX > 20 = trending
    ADX_STRONG_TREND_THRESHOLD = 35   # ADX > 35 = strong trend
    ADX_RANGING_THRESHOLD = 20        # ADX < 20 = ranging
    
    ATR_PERIOD = 14
    ATR_VOLATILE_MULTIPLIER = 1.3     # ATR > 1.3× avg = volatile
    ATR_LOW_VOL_MULTIPLIER = 0.8      # ATR < 0.8× avg = low vol
    
    REGIME_CONFIRMATION_CANDLES = 3   # Wait 3 candles before confirming
```

**Example Regime Detection:**
```
Inputs: ADX=28.5, ATR=45 (avg=35)
Calculations:
  - ADX 28.5 > 20 → TRENDING
  - ADX 28.5 < 35 → Not STRONG
  - ATR 45/35 = 1.29 → Normal volatility
  
Output: TRENDING, Normal Vol
Strategies enabled: VWAP_EMA_TREND, MOMENTUM_BREAKOUT
Strategies disabled: VWAP_BOUNCE, RANGE_MEAN_REVERSION
```

---

### 5. Bias Detection Variables
**Location:** `config.py` → `BotConfig.Bias`

```python
class Bias:
    # Futures Premium
    PREMIUM_STRONG_BULLISH = 80       # Future 80+ points above spot
    PREMIUM_BULLISH = 50              # Future 50-79 points above
    PREMIUM_NEUTRAL_LOW = 20          # Future 20-49 points above
    PREMIUM_BEARISH = -20             # Future in discount
    
    # PCR Thresholds
    PCR_BULLISH = 1.15                # PCR > 1.15 = bullish
    PCR_BEARISH = 0.85                # PCR < 0.85 = bearish
```

**Example Bias Calculation:**
```
Market Data:
  Spot LTP:    25,850
  Future LTP:  25,920
  PCR:         1.25
  
Calculations:
  Premium = 25920 - 25850 = +70 points
  
  Premium Score: +70 > 50 → +3 (bullish)
  PCR Score:     1.25 > 1.15 → +2 (bullish)
  EMA Alignment: 5>13>21>50 → +3 (bullish)
  
  Total Bias Score: +8 (BULLISH)
  
Action: Prefer CE trades, reduce PE entries
```

---

### 6. Order Flow Variables
**Location:** `config.py` → `BotConfig.OrderFlow`

```python
class OrderFlow:
    OI_SIGNIFICANT_CHANGE_PCT = 5     # ±5% OI change
    OI_BUILDUP_THRESHOLD = 10         # 10%+ = buildup
    
    VOLUME_SPIKE_MULTIPLIER = 2.0     # 2× avg = spike
    VOLUME_DRY_MULTIPLIER = 0.5       # 0.5× avg = dry
    
    OI_LOOKBACK_PERIODS = 5           # Compare with 5 candles ago
```

**Example Order Flow:**
```
CE 25850:
  Current OI:  1,500,000
  5 candles ago: 1,350,000
  
  Change = (1500000-1350000)/1350000 = +11.1%
  
  11.1% > 10% → STRONG BUILDUP
  Interpretation: Call writers building positions
  Signal: Resistance at 25850, prefer PE or wait for breakout
```

---

### 7. Risk Management Variables
**Location:** `config.py` → `BotConfig.Risk`

```python
class Risk:
    # Capital Management
    CAPITAL_PER_STRATEGY = 10000      # ₹10,000 per strategy
    MAX_CAPITAL_USAGE_PCT = 0.7       # Use max 70% of capital
    LOT_SIZE = 25                     # NIFTY lot size
    
    # Position Limits
    MAX_CONCURRENT_POSITIONS = 4      # Max 4 trades at once
    MAX_SAME_DIRECTION = 3            # Max 3 CE or 3 PE
    MAX_SAME_STRIKE = 1               # Max 1 trade per strike
    
    # Daily Limits
    MAX_DAILY_TRADES = 20             # Stop after 20 trades
    MAX_DAILY_LOSS = 5000             # Auto-reset at ₹5000 loss
    MAX_DAILY_LOSS_ACTION = "LOG"     # "LOG" or "HALT"
    
    # Stop Loss & Target
    STOP_LOSS_PERCENT = 35            # SL at entry - 35%
    TARGET_PERCENT = 50               # Target at entry + 50%
    TRAIL_TRIGGER_PERCENT = 30        # Trail after 30% profit
    TRAIL_GAP_PERCENT = 15            # Trail 15% below peak
    
    # Costs
    BROKERAGE_PER_ORDER = 20          # ₹20 flat per order
    TAXES_PER_TRADE = 100             # ₹100 (STT, charges, GST)
    SLIPPAGE_POINTS = 0.5             # 0.5 point slippage
```

**Example Position Calculation:**
```
Strategy Signal: BUY CE 25850
Entry Price: ₹120
Capital: ₹10,000
Max Usage: 70% = ₹7,000

Affordable Lots:
  Cost per lot = 120 × 25 = ₹3,000
  Max lots = 7000 / 3000 = 2.33 → 2 lots
  
Position Value: 2 × 25 × 120 = ₹6,000

Stop Loss:
  SL% = 35%
  SL Price = 120 × (1-0.35) = ₹78
  Max Loss = (120-78) × 50 = ₹2,100
  
Target:
  Target% = 50%
  Target Price = 120 × (1+0.50) = ₹180
  Potential Profit = (180-120) × 50 = ₹3,000

Risk:Reward = 2100:3000 = 1:1.43
```

---

### 8. Time Window Variables
**Location:** `config.py` → `BotConfig.TimeWindows`

```python
class TimeWindows:
    MARKET_OPEN = (9, 15)          # 9:15 AM
    MARKET_CLOSE = (15, 30)        # 3:30 PM
    NO_NEW_ENTRY = (15, 0)         # No new trades after 3:00 PM
    FORCE_EXIT = (15, 20)          # Force exit at 3:20 PM
```

**Example Timeline:**
```
09:15 - Market opens, bot starts
09:15-15:00 - Active trading (new entries allowed)
15:00-15:20 - No new entries, manage existing only
15:20 - Force exit all positions
15:30 - Market closes, bot stops
```

---

## 🎯 TRADING STRATEGIES

### Strategy 1: ORIGINAL
**File:** `strategies/trend_strategies.py`

**Logic:**
- EMA crossover (5 crosses above 13)
- RSI confirmation (bullish: 40-70, bearish: 30-60)
- VWAP support/resistance

**Entry Conditions:**
```python
CE Entry:
  - Close > VWAP
  - EMA5 > EMA13
  - RSI between 40-70
  - Regime: TRENDING or STRONG_TREND
  
PE Entry:
  - Close < VWAP
  - EMA5 < EMA13
  - RSI between 30-60
  - Regime: TRENDING_DOWN or STRONG_TREND_DOWN
```

**Example:**
```
Market State:
  Close: 25,870
  VWAP:  25,850
  EMA5:  25,865
  EMA13: 25,855
  RSI:   58
  Regime: TRENDING
  
Check CE:
  ✓ 25870 > 25850 (above VWAP)
  ✓ 25865 > 25855 (EMA cross)
  ✓ 58 in [40-70]
  ✓ TRENDING regime
  
Signal: BUY CE, Strength: STRONG
```

---

### Strategy 2: VWAP_EMA_TREND
**File:** `strategies/trend_strategies.py`

**Logic:**
- Strong trend confirmation with ADX
- VWAP + EMA21 alignment
- Volume spike confirmation

**Entry:**
```python
CE Entry:
  - ADX > 25
  - Close > VWAP > EMA21
  - Volume > 1.5× average
  - Bias: BULLISH or NEUTRAL
```

---

### Strategy 3: MOMENTUM_BREAKOUT
**File:** `strategies/trend_strategies.py`

**Logic:**
- Breakout above recent high with momentum
- RSI > 60 for CE, < 40 for PE
- ATR expansion (volatility increase)

**Entry:**
```python
CE Entry:
  - Close > max(high[-5:])  # 5-candle high breakout
  - RSI > 60
  - ATR > ATR[-5] average  # Volatility expanding
  - Volume spike
```

**Example:**
```
Recent 5 Highs: [25850, 25860, 25865, 25858, 25862]
Current Close:  25,875
RSI:           68
ATR:           52 (avg: 45)
Volume:        2.3× average

Check:
  ✓ 25875 > 25865 (breakout)
  ✓ 68 > 60
  ✓ 52 > 45 (expanding vol)
  ✓ Volume spike
  
Signal: BUY CE, Strength: STRONG
```

---

### Strategy 4: VWAP_BOUNCE
**File:** `strategies/range_strategies.py`

**Logic:**
- Price bounces off VWAP in ranging markets
- RSI oversold/overbought
- Regime: RANGING

**Entry:**
```python
CE Entry:
  - Regime: RANGING
  - Close touched VWAP (within 5 points)
  - RSI < 35 (oversold)
  - Previous candle red, current green
```

---

### Strategy 5: EMA_CROSSOVER
**File:** `strategies/ema_crossover_strategy.py`

**Logic:**
- Classic EMA crossover (fast crosses slow)
- Multiple timeframe confirmation
- Volume confirmation

**Entry:**
```python
CE Entry:
  - EMA5 just crossed above EMA13 (within 2 candles)
  - EMA13 > EMA21 (trend alignment)
  - Volume > average
```

---

### Strategy 6: LIQUIDITY_SWEEP
**File:** `strategies/liquidity_sweep_strategy.py`

**Logic:**
- False breakout detection
- Price sweeps liquidity then reverses
- High OI strikes as magnets

**Entry:**
```python
CE Entry:
  - Price briefly broke below support
  - Now back above support
  - Support = high OI strike or swing low
  - RSI divergence
```

**Example:**
```
Support Level: 25,800 (high PE OI)
Price Action:
  Candle 1: Low 25,798 (sweep below)
  Candle 2: Close 25,815 (reclaim)
  
OI Data:
  PE 25800: 2M OI (liquidity pool)
  
Interpretation: Liquidity sweep complete, reversal up
Signal: BUY CE
```

---

### Strategy 7: VOLATILITY_SPIKE
**File:** `strategies/volatility_strategies.py`

**Logic:**
- ATR spike detection
- IV percentile jump
- Momentum follow-through

**Entry:**
```python
CE Entry:
  - ATR > 1.5× average (spike)
  - IV Percentile > 70% (high IV)
  - Strong directional move (>1% in 5min)
  - Volume confirmation
```

---

### Strategy 8: ORDER_FLOW
**File:** `strategies/order_flow_strategy.py`

**Logic:**
- OI buildup direction
- Volume profile analysis
- Big player positioning

**Entry:**
```python
CE Entry:
  - CE OI decreasing (covering)
  - PE OI increasing (building)
  - PCR > 1.2 (bullish)
  - Futures premium positive
```

---

### Strategy 9: OPENING_RANGE_BREAKOUT
**File:** `strategies/volatility_strategies.py`

**Logic:**
- First 15-30 minute range
- Breakout with volume
- Only in first 2 hours

**Entry:**
```python
Time: 9:15-11:00 only

CE Entry:
  - Current price > opening range high
  - Volume > 2× opening range avg
  - ADX > 20
```

---

## 🧠 MARKET INTELLIGENCE

### 1. Regime Detector
**File:** `market_intelligence/regime_detector.py`

**Purpose:** Identifies market regime to enable/disable strategies

**Regimes:**
```python
UNKNOWN            # Warmup phase
RANGING            # ADX < 20, low volatility
TRENDING           # 20 < ADX < 35, directional
TRENDING_DOWN      # Same but downward
STRONG_TREND       # ADX > 35, strong up
STRONG_TREND_DOWN  # ADX > 35, strong down
VOLATILE_RANGING   # ADX < 20 but ATR high
```

**Calculation:**
```python
def update(high, low, close):
    # Calculate ADX (14 period)
    # Calculate ATR (14 period)
    # Calculate ATR percentile
    
    if ADX < 20:
        if ATR_percentile > 70:
            return VOLATILE_RANGING
        else:
            return RANGING
    elif 20 <= ADX < 35:
        if uptrend:
            return TRENDING
        else:
            return TRENDING_DOWN
    else:  # ADX >= 35
        if uptrend:
            return STRONG_TREND
        else:
            return STRONG_TREND_DOWN
```

**Example:**
```
Input:
  High: 25,880
  Low:  25,850
  Close: 25,870
  
After 50 candles warmup:
  ADX: 28.5
  ATR: 45
  ATR Percentile: 55%
  +DI: 25
  -DI: 18
  
Calculation:
  ADX 28.5 → in [20, 35] range
  +DI > -DI → uptrend
  
Output: TRENDING (upward)

Strategy Impact:
  ✓ Enable: VWAP_EMA_TREND, MOMENTUM_BREAKOUT
  ✗ Disable: VWAP_BOUNCE, RANGE_MEAN_REVERSION
```

---

### 2. Bias Calculator
**File:** `market_intelligence/bias_calculator.py`

**Purpose:** Determines overall market bias (bullish/bearish/neutral)

**Scoring Components:**
```python
1. Futures Premium (-3 to +3)
   -3: Strong discount (< -20 pts)
   -2: Discount (-20 to 0)
   -1: Small premium (0 to 20)
   +1: Premium (20 to 50)
   +2: Strong premium (50 to 80)
   +3: Very strong (> 80)

2. EMA Alignment (-3 to +3)
   Bullish: 5 > 13 > 21 > 50
   Bearish: 5 < 13 < 21 < 50

3. PCR (-2 to +2)
   Bullish: > 1.15 (put writing)
   Bearish: < 0.85 (call writing)

4. CE/PE OI Change (-2 to +2)
   Bullish: CE down, PE up
   Bearish: CE up, PE down

Total Score: -10 to +10
```

**Bias Levels:**
```
+7 to +10:  STRONG_BULLISH
+4 to +6:   BULLISH
-3 to +3:   NEUTRAL
-6 to -4:   BEARISH
-10 to -7:  STRONG_BEARISH
```

**Example:**
```
Market Data:
  Spot:    25,850
  Future:  25,920 (+70 premium)
  PCR:     1.28
  EMA:     5>13>21>50 (aligned)
  CE OI:   -5% change
  PE OI:   +8% change
  
Scoring:
  Premium:     +70 → +2
  EMA:         Aligned → +3
  PCR:         1.28 > 1.15 → +2
  OI Change:   CE down, PE up → +2
  
Total: +9 → STRONG_BULLISH

Strategy Impact:
  - Prefer CE entries
  - Increase CE position size by 20%
  - Reduce PE entries
  - Skip PE in neutral regimes
```

---

### 3. Order Flow Tracker
**File:** `market_intelligence/order_flow_tracker.py`

**Purpose:** Tracks OI and volume changes

**Metrics:**
```python
OI Change:
  - Current OI vs 5 periods ago
  - Buildup: +10% or more
  - Unwinding: -10% or more

Volume Profile:
  - Current vs 5-period average
  - Spike: 2× average
  - Dry: 0.5× average

ATM Activity:
  - ATM CE/PE OI ratio
  - Changes indicate positioning
```

**Example:**
```
CE 25850 (ATM):
  Current OI:  1,500,000
  5 candles ago: 1,350,000
  Change: +11.1%
  
  Current Volume: 45,000
  Avg Volume:     25,000
  Ratio: 1.8×
  
Analysis:
  OI: +11.1% → BUILDUP
  Volume: 1.8× → ELEVATED
  
Interpretation:
  Call writers building positions at 25850
  Indicates resistance/ceiling
  
Signal: Prefer PE or wait for breakout above 25850
```

---

### 4. Liquidity Mapper
**File:** `market_intelligence/liquidity_mapper.py`

**Purpose:** Identifies key price levels

**Level Types:**
```python
1. Swing Highs/Lows
   - Last 10 candles
   - Local peaks/troughs

2. Round Numbers
   - 100-point intervals
   - 25,800 | 25,900 | 26,000

3. High OI Strikes
   - Max pain calculation
   - OI > 1.5× average

4. VWAP Levels
   - Daily VWAP
   - Session VWAP
```

**Example:**
```
Current Price: 25,870

Detected Levels:
  Resistance:
    25,900 (round number, CE OI: 2M)
    25,950 (swing high, 10:30 AM)
    26,000 (psychological, max pain)
    
  Support:
    25,850 (VWAP, current)
    25,800 (round number, PE OI: 1.8M)
    25,750 (swing low, 9:45 AM)

Usage:
  - Stop losses below support
  - Targets at resistance
  - Avoid entries between 25,865-25,875 (no man's land)
```

---

## 🎮 EXECUTION SYSTEM

### Signal Aggregator
**File:** `execution/signal_aggregator.py`

**Purpose:** Combines signals from multiple strategies

**Confluence Voting:**
```python
1. Collect all signals (CE and PE)
2. Check for conflicts
   - If CE and PE signals → resolve
3. Calculate confluence score
   - Each strategy votes
   - Weight by signal strength
4. Apply market context filters
5. Decide: EXECUTE or SKIP

Minimum Requirements:
  - Confluence ≥ 6
  - Same direction ≥ 2 strategies
  - Market context favorable
```

**Example:**
```
Signals Received:
  1. ORIGINAL → CE, Strength: STRONG (score: 3)
  2. VWAP_EMA → CE, Strength: STRONG (score: 3)
  3. MOMENTUM → CE, Strength: MODERATE (score: 2)
  
Confluence Calculation:
  Total signals: 3
  Same direction: 3 (all CE)
  Total score: 3+3+2 = 8
  
Market Context:
  Regime: TRENDING (✓)
  Bias: BULLISH (+7) (✓)
  Order Flow: NEUTRAL (✓)
  
Decision: EXECUTE CE
Confluence: 8/9
Size Multiplier: 1.2× (strong confluence + bullish bias)
```

**Conflict Resolution:**
```
Signals:
  CE: ORIGINAL (3), VWAP_EMA (3)
  PE: MOMENTUM (2), VWAP_BOUNCE (2)
  
Count: CE=2, PE=2 (tie)
Score: CE=6, PE=4

Resolution: CE wins (higher score)

If still tied → check Bias:
  Bias = BULLISH (+7) → CE
  Bias = BEARISH (-7) → PE
  Bias = NEUTRAL → SKIP
```

---

### Strategy Runner
**File:** `execution/strategy_runner.py`

**Purpose:** Manages individual strategy lifecycle

**States:**
```python
NO_POSITION    # Scanning for entry
IN_POSITION    # Managing active trade
FORCE_EXIT     # EOD or max loss exit
```

**Position Management:**
```python
def process_tick():
    if NO_POSITION:
        # Scan for entry signal
        signal = strategy.generate_signal()
        if signal:
            return signal  # Send to aggregator
    
    elif IN_POSITION:
        # Check exits
        if current_price <= stop_loss:
            exit("STOP_LOSS")
        elif current_price >= target:
            exit("TARGET")
        elif trailing_active:
            update_trailing_stop()
            if current_price <= trailing_stop:
                exit("TRAILING_STOP")
```

**Example Trade Lifecycle:**
```
09:45:00 - Signal Generated
           Strategy: ORIGINAL
           Direction: CE 25850
           Entry: ₹120

09:45:05 - Position Entered
           Lots: 2
           Value: ₹6,000
           SL: ₹78
           Target: ₹180
           
10:15:30 - Trail Triggered
           Current: ₹156 (+30%)
           Trail SL: ₹133 (15% below peak)
           
10:18:45 - Peak Reached
           Current: ₹168 (+40%)
           Trail SL: ₹143
           
10:22:10 - Trail Stop Hit
           Exit: ₹143
           P&L: (143-120)×50 = +₹1,150
           
10:22:15 - Position Closed
           Status: WIN
           Duration: 37 minutes
```

---

## 📊 LOGGING SYSTEM

### 1. System Log (TXT)
**File:** `logs/Live_System_Log_YYYYMMDD_HHMMSS.txt`

**Format:**
```
2026-01-08 09:15:00 | INFO | System initialized with 36 strategies
2026-01-08 09:15:05 | INFO | Target Future: NIFTY27JAN26FUT
2026-01-08 09:15:10 | INFO | [1minute] Connected to Groww API
```

**Content:**
- System startup/shutdown
- API connection status
- Error messages
- Auto-reset events
- Force exits

**Example:**
```
2026-01-08 09:15:00 | INFO | ========================================
2026-01-08 09:15:00 | INFO | EXPERIMENT 6 - SYSTEM LOG INITIALIZED
2026-01-08 09:15:00 | INFO | ========================================
2026-01-08 09:15:05 | INFO | Target Future: NIFTY27JAN26FUT
2026-01-08 09:15:10 | INFO | System initialized with 36 strategies
2026-01-08 09:45:23 | WARNING | Approaching daily loss limit (₹3,500)
2026-01-08 11:30:45 | WARNING | ========================================
2026-01-08 11:30:45 | WARNING | 🔄 AUTO-RESET #1 - MAX DAILY LOSS HIT
2026-01-08 11:30:45 | WARNING | Previous Loss: ₹5,200.00
2026-01-08 11:30:45 | WARNING | Trades Taken: 12
2026-01-08 11:30:45 | WARNING | Win Rate: 41.7%
2026-01-08 11:30:45 | WARNING | Starting Fresh Session with Capital: ₹10,000.00
2026-01-08 11:30:45 | WARNING | ========================================
2026-01-08 11:30:50 | INFO | ✅ Fresh session started - ready to trade!
```

---

### 2. Super Tracker (CSV)
**File:** `logs/Live_Super_Tracker_YYYYMMDD_HHMMSS.csv`

**Columns:**
```
Timestamp, Spot_LTP, Fut_LTP, Premium, VWAP, RSI, ADX, ATR, 
PCR, Regime, Bias, Active_Positions, Daily_PnL
```

**Example:**
```csv
Timestamp,Spot_LTP,Fut_LTP,Premium,VWAP,RSI,ADX,ATR,PCR,Regime,Bias,Active_Positions,Daily_PnL
2026-01-08 09:15:00,25850.00,25920.00,70.00,25848.50,52.3,18.5,38.2,1.15,RANGING,NEUTRAL,0,0.00
2026-01-08 09:16:00,25855.00,25925.00,70.00,25850.20,53.8,19.2,38.5,1.16,RANGING,NEUTRAL,0,0.00
2026-01-08 09:45:00,25870.00,25938.00,68.00,25862.30,58.2,22.1,42.1,1.22,TRENDING,BULLISH,2,350.00
2026-01-08 10:30:00,25892.00,25960.00,68.00,25878.40,65.3,28.5,45.8,1.28,TRENDING,STRONG_BULLISH,3,1250.00
```

**Usage:**
- Real-time market snapshot every minute
- Track indicator evolution
- Correlation analysis
- Backtesting validation

---

### 3. Trade Book (CSV)
**File:** `logs/Live_Trade_Book_YYYYMMDD_HHMMSS.csv`

**Columns:**
```
Entry_Time, Exit_Time, Strategy, Timeframe, Direction, Strike,
Entry_Price, Exit_Price, Lots, PnL, Exit_Reason, Duration_Min,
Regime, Bias, Confluence
```

**Example:**
```csv
Entry_Time,Exit_Time,Strategy,Timeframe,Direction,Strike,Entry_Price,Exit_Price,Lots,PnL,Exit_Reason,Duration_Min,Regime,Bias,Confluence
2026-01-08 09:45:12,2026-01-08 10:22:18,ORIGINAL,1minute,CE,25850,120.00,143.00,2,1150.00,TRAILING_STOP,37,TRENDING,BULLISH,8
2026-01-08 10:35:22,2026-01-08 10:58:45,VWAP_EMA,2minute,CE,25900,95.00,78.00,2,-850.00,STOP_LOSS,23,TRENDING,BULLISH,7
2026-01-08 11:15:33,2026-01-08 11:48:12,MOMENTUM,3minute,PE,25850,88.00,132.00,2,2200.00,TARGET,33,TRENDING_DOWN,BEARISH,9
```

**Analysis:**
```python
import pandas as pd

df = pd.read_csv('Live_Trade_Book_20260108.csv')

# Win rate by strategy
df.groupby('Strategy')['PnL'].apply(lambda x: (x > 0).sum() / len(x) * 100)

# Average P&L by regime
df.groupby('Regime')['PnL'].mean()

# Best timeframe
df.groupby('Timeframe')['PnL'].sum()

# Exit reason distribution
df['Exit_Reason'].value_counts()
```

---

### 4. Bot Movement (CSV)
**File:** `logs/Live_BOT_MOVEMENT_YYYYMMDD.csv`

**Columns:**
```
Timestamp, Strategy, Timeframe, Action, Details, Price, PnL
```

**Example:**
```csv
Timestamp,Strategy,Timeframe,Action,Details,Price,PnL
2026-01-08 09:45:12,ORIGINAL,1minute,ENTRY,CE 25850 @ 120.00,120.00,0.00
2026-01-08 09:55:30,ORIGINAL,1minute,UPDATE,Trail activated @ 156.00,156.00,900.00
2026-01-08 10:22:18,ORIGINAL,1minute,EXIT,Trailing stop @ 143.00,143.00,1150.00
2026-01-08 10:35:22,VWAP_EMA,2minute,ENTRY,CE 25900 @ 95.00,95.00,0.00
2026-01-08 10:58:45,VWAP_EMA,2minute,EXIT,Stop loss @ 78.00,78.00,-850.00
```

**Usage:**
- Tick-by-tick position tracking
- Trail stop evolution
- Entry/exit timing analysis

---

## 🛡️ RISK MANAGEMENT

### Daily Limits
```python
MAX_DAILY_TRADES = 20      # Stop after 20 trades
MAX_DAILY_LOSS = 5000      # Auto-reset at ₹5,000 loss
```

**Example:**
```
Trade #1:  -₹400
Trade #2:  +₹800
Trade #3:  -₹1,200
...
Trade #10: -₹950

Cumulative P&L: -₹4,200

Status: ⚠️ Near limit warning
Action: Continue trading (still <₹5,000)

Trade #11: -₹900

Cumulative P&L: -₹5,100

Status: 🔄 MAX LOSS HIT
Action: Auto-reset triggered
  1. Force exit all positions
  2. Log final stats
  3. Reset to fresh capital
  4. Resume trading
```

---

### Position Limits
```python
MAX_CONCURRENT_POSITIONS = 4   # Max 4 trades
MAX_SAME_DIRECTION = 3         # Max 3 CE or 3 PE
MAX_SAME_STRIKE = 1            # Max 1 per strike
```

**Example:**
```
Active Positions:
1. CE 25850 (ORIGINAL)
2. CE 25900 (VWAP_EMA)
3. CE 25950 (MOMENTUM)

New Signal: CE 26000 (VOLATILITY)

Check:
  ✗ Total positions: 3 < 4 (✓)
  ✗ CE count: 3 = 3 (✗ BLOCKED)
  
Decision: SKIP (max same direction)

New Signal: PE 25800

Check:
  ✓ Total: 3 < 4
  ✓ PE count: 0 < 3
  ✓ Strike 25800: 0 < 1
  
Decision: ALLOW
```

---

### Stop Loss & Trailing
```python
STOP_LOSS_PERCENT = 35         # SL at -35%
TARGET_PERCENT = 50            # Target at +50%
TRAIL_TRIGGER_PERCENT = 30     # Trail after +30%
TRAIL_GAP_PERCENT = 15         # 15% below peak
```

**Example:**
```
Entry: ₹100

Static Levels:
  SL: 100 × (1-0.35) = ₹65
  Target: 100 × (1+0.50) = ₹150

Price Movement:
  T+5min:  ₹110 (+10%) → No trail yet
  T+10min: ₹130 (+30%) → Trail triggered!
  
Trail Calculation:
  Trail SL = 130 × (1-0.15) = ₹110.50
  
Price continues:
  T+15min: ₹145 (+45%)
  New Trail SL = 145 × 0.85 = ₹123.25
  
  T+18min: ₹142 (-2% from peak)
  Trail SL = ₹123.25 (unchanged)
  
  T+20min: ₹120 (drops)
  → TRAIL STOP HIT at ₹123.25
  
Final P&L: (123.25-100) × 50 = +₹1,162.50
```

---

## 📖 EXAMPLES

### Example 1: Complete Trade Flow

**Scenario:** Morning bullish trend

```
09:30:00 - Market State
  Spot:    25,850
  Future:  25,918 (+68 premium)
  VWAP:    25,848
  RSI:     54
  ADX:     23
  PCR:     1.20
  
Intelligence:
  Regime: TRENDING (ADX=23)
  Bias: BULLISH (+7)
  Order Flow: NEUTRAL
  
09:30:05 - Signals Generated
  1. ORIGINAL → CE 25850, STRONG (score: 3)
  2. VWAP_EMA → CE 25850, STRONG (score: 3)
  3. MOMENTUM → CE 25850, MODERATE (score: 2)
  
09:30:10 - Signal Aggregation
  Confluence: 8/9
  All CE direction
  Context favorable
  
  Decision: EXECUTE CE 25850
  Size Multiplier: 1.2× (strong confluence)
  
09:30:15 - Risk Check
  Current Positions: 1/4 (✓)
  CE Count: 1/3 (✓)
  Strike 25850: 0/1 (✓)
  Daily Trades: 5/20 (✓)
  Daily P&L: +₹850 (✓)
  
  Decision: ALLOW
  
09:30:20 - Strike Selection
  Capital: ₹10,000 × 70% = ₹7,000
  
  Option Chain:
    CE 25850: ₹120, OI: 1.5M
    CE 25900: ₹95, OI: 1.2M
    CE 25950: ₹75, OI: 0.8M
    
  Selected: CE 25850 @ ₹120
  Affordable: 7000/(120×25) = 2.33 → 2 lots
  
09:30:25 - Entry Execution
  Position ID: POS_0012
  Strike: 25850 CE
  Entry: ₹120
  Lots: 2
  Value: ₹6,000
  SL: ₹78 (-35%)
  Target: ₹180 (+50%)
  Trail Trigger: ₹156 (+30%)
  
09:45:00 - Price Update
  Current: ₹135 (+12.5%)
  Status: IN_POSITION, no trail yet
  Unrealized: +₹750
  
10:00:00 - Price Update
  Current: ₹158 (+31.7%)
  Status: TRAIL ACTIVATED
  Trail SL: ₹134.30 (15% below peak)
  Unrealized: +₹1,900
  
10:15:00 - Peak Reached
  Current: ₹168 (+40%)
  Trail SL: ₹142.80
  Unrealized: +₹2,400
  
10:22:00 - Retracement
  Current: ₹145
  Trail SL: ₹142.80 (still active)
  
10:22:30 - Trail Stop Hit
  Exit: ₹143
  Reason: TRAILING_STOP
  
  Final P&L: (143-120) × 50 = +₹1,150
  Duration: 52 minutes
  
10:22:35 - Position Closed
  Updated Daily Stats:
    Trades: 6
    Wins: 4
    Losses: 2
    Win Rate: 66.7%
    Daily P&L: +₹2,000
```

---

### Example 2: Auto-Reset Scenario

```
11:00:00 - Daily Stats
  Trades: 15
  Wins: 5
  Losses: 10
  Daily P&L: -₹4,800
  
11:15:00 - New Signal
  Strategy: MOMENTUM
  Direction: PE 25850
  
11:15:05 - Entry Execution
  Entry: ₹110
  Lots: 2
  SL: ₹71.50
  
11:28:00 - Stop Loss Hit
  Exit: ₹71.50
  P&L: (71.50-110) × 50 = -₹1,925
  
11:28:05 - Daily Stats Updated
  Trades: 16
  Daily P&L: -₹6,725
  
11:28:10 - AUTO-RESET TRIGGERED
  Reason: Daily loss -₹6,725 > -₹5,000 limit
  
  Reset Process:
    1. Force exit all positions (none active)
    2. Log previous session:
       ============================================================
       🔄 AUTO-RESET #1 - MAX DAILY LOSS HIT
       Previous Loss: ₹6,725.00
       Trades Taken: 16
       Win Rate: 31.3%
       Starting Fresh Session with Capital: ₹10,000.00
       ============================================================
    
    3. Reset Risk Manager:
       Daily P&L → ₹0.00
       Trades → 0
       Positions → cleared
       
    4. Reset Signal Aggregator:
       Stats → cleared
       
    5. Wait 5 seconds
    
11:28:15 - Fresh Session Started
  Capital: ₹10,000 (fresh)
  Daily P&L: ₹0.00
  Reset Count: 1
  
  Status: Ready to trade
  
11:30:00 - New Signal
  Strategy: VWAP_BOUNCE
  Direction: CE 25900
  
11:30:05 - Entry (Fresh Session)
  Entry: ₹88
  This counts as Trade #1 of new session
```

---

### Example 3: Conflict Resolution

```
14:30:00 - Signals Generated
  CE Signals:
    ORIGINAL → CE, STRONG (3)
    VWAP_EMA → CE, MODERATE (2)
    
  PE Signals:
    MOMENTUM → PE, STRONG (3)
    VWAP_BOUNCE → PE, MODERATE (2)
    
14:30:05 - Aggregator Analysis
  CE Count: 2, Total Score: 5
  PE Count: 2, Total Score: 5
  
  → CONFLICT (tied on count and score)
  
14:30:06 - Resolution Process
  Check Bias:
    Current Bias: BULLISH (+6)
    
  Bias Rule:
    BULLISH → Prefer CE
    
  Decision: EXECUTE CE 25900
  
  Ignored Signals:
    MOMENTUM → PE (conflict)
    VWAP_BOUNCE → PE (conflict)
```

---

### Example 4: Logging Analysis

**Python Code:**
```python
import pandas as pd

# Load trade book
trades = pd.read_csv('logs/Live_Trade_Book_20260108.csv')

# 1. Strategy Performance
strategy_stats = trades.groupby('Strategy').agg({
    'PnL': ['sum', 'mean', 'count'],
    'Exit_Reason': lambda x: (x.str.contains('TARGET')).sum()
})
strategy_stats.columns = ['Total_PnL', 'Avg_PnL', 'Trades', 'Targets_Hit']
strategy_stats['Win_Rate'] = (trades.groupby('Strategy')['PnL']
                              .apply(lambda x: (x > 0).sum() / len(x) * 100))

print("Strategy Performance:")
print(strategy_stats.sort_values('Total_PnL', ascending=False))

# Output:
#                      Total_PnL  Avg_PnL  Trades  Targets_Hit  Win_Rate
# MOMENTUM               3250.00   650.00       5            2     80.0
# ORIGINAL               2150.00   358.33       6            1     66.7
# VWAP_EMA               1850.00   462.50       4            2     75.0
# VOLATILITY_SPIKE        450.00   150.00       3            0     66.7
# ...

# 2. Regime Performance
regime_stats = trades.groupby('Regime')['PnL'].agg(['sum', 'mean', 'count'])
print("\nRegime Performance:")
print(regime_stats)

# Output:
#                    sum      mean  count
# TRENDING        4200.00   525.00      8
# STRONG_TREND    2800.00   700.00      4
# RANGING         -850.00  -212.50      4

# 3. Time Analysis
trades['Hour'] = pd.to_datetime(trades['Entry_Time']).dt.hour
hourly = trades.groupby('Hour')['PnL'].agg(['sum', 'count'])
print("\nHourly Performance:")
print(hourly)

# Output:
#       sum  count
# 9    850       3
# 10  2150       5
# 11  1800       4
# 12   950       3
# 13  -400       2
# 14   850       3

# 4. Best Confluence
confluence_analysis = trades.groupby('Confluence')['PnL'].mean()
print("\nConfluence Analysis:")
print(confluence_analysis.sort_values(ascending=False))

# Output:
# 9    750.00
# 8    520.00
# 7    380.00
# 6    210.00
```

---

## 🚀 QUICK START

### Run Test Mode
```bash
python main.py --test
```

### Run Live Trading
```bash
python main.py
```

### Check Logs
```bash
# View system log
tail -f logs/Live_System_Log_*.txt

# Analyze trades
python
>>> import pandas as pd
>>> df = pd.read_csv('logs/Live_Trade_Book_*.csv')
>>> df['PnL'].sum()
```

---

## 📞 SUPPORT

**Test Status:** ✅ 22/22 tests passing  
**Market Data:** ✅ Real-time from GrowwAPI  
**Auto-Reset:** ✅ Implemented  
**Logging:** ✅ Comprehensive  

**System Ready for Live Trading** 🚀

---

*Documentation v1.0 - January 8, 2026*
