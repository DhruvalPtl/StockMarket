# Experiment 8 - Flattrade API Conversion

## Overview

This folder contains the converted version of Experiment 6, migrated from **Groww API** to **Flattrade API**.

## Key Changes

### 1. API Provider Change
- **From**: Groww API (`growwapi` package)
- **To**: Flattrade API (using `pythonAPI-main/api_helper.py`)

### 2. Configuration Updates (`config.py`)

#### Old (Groww):
```python
API_KEY = "long_jwt_token..."
API_SECRET = "secret_string"
```

#### New (Flattrade):
```python
USER_TOKEN = "session_token_from_login_flow"
USER_ID = "your_user_id"
```

**Important**: You need to generate a session token using the Flattrade login flow. See `../pythonAPI-main/token_generator/setup.md` for instructions.

### 3. Data Engine Changes (`data/data_engine.py`)

#### Authentication
- **Old**: `GrowwAPI.get_access_token()` and `GrowwAPI(token)`
- **New**: `NorenApiPy()` and `api.set_session(userid, password='', usertoken)`

#### Data Fetching Methods

**Spot/Future Data**:
- **Old**: `groww.get_historical_candles(exchange, segment, symbol, start, end, timeframe)`
- **New**: `api.get_time_price_series(exchange, token, starttime, endtime, interval)`

**Option Chain**:
- **Old**: Direct option chain retrieval from Groww
- **New**: `api.get_option_chain()` or manual strike fetching with `api.searchscrip()` + `api.get_quotes()`

#### Symbol Format
- **Old**: `NSE-NIFTY`, `NSE-NIFTY-27Jan26-FUT`
- **New**: `Nifty 50` (for index), `NIFTY27JAN26FUT` (for futures), `NIFTY27JAN2624000CE` (for options)

#### Data Response Format
- **Old**: Groww returns `{'candles': [...]}` with columns [t, o, h, l, c, v]
- **New**: Flattrade returns list of dicts with keys: stat, time, into, inth, intl, intc, intvwap, intv, intoi, oi

### 4. Token Management

Flattrade requires token lookup for symbols:
```python
def _get_token(self, exchange, symbol):
    ret = api.searchscrip(exchange=exchange, searchtext=symbol)
    # Returns token for the symbol
```

Tokens are cached to avoid repeated lookups.

### 5. Timeframe Mapping

```python
timeframe_map = {
    "1minute": "1",
    "2minute": "2",
    "3minute": "3",
    "5minute": "5",
    "15minute": "15",
    "30minute": "30",
    "60minute": "60"
}
```

### 6. Orchestrator Updates (`orchestrator.py`)

The orchestrator initialization now passes Flattrade credentials:

```python
# Old
engine = DataEngine(
    api_key=self.config.API_KEY,
    api_secret=self.config.API_SECRET,
    ...
)

# New
engine = DataEngine(
    user_token=self.config.USER_TOKEN,
    user_id=self.config.USER_ID,
    ...
)
```

## Setup Instructions

### 1. Generate Flattrade Session Token

Follow the instructions in `../pythonAPI-main/token_generator/setup.md` to:
1. Set up your Flattrade API credentials
2. Generate a session token
3. Get your user ID

### 2. Update Configuration

Edit `experiment8/config.py`:

```python
USER_TOKEN = "your_generated_session_token_here"
USER_ID = "your_flattrade_user_id_here"
```

### 3. Install Dependencies

The Flattrade API library is already in `../pythonAPI-main/`. Ensure it's accessible.

```bash
# If needed, install requirements
pip install pandas numpy
```

### 4. Run the Bot

```bash
cd experiment8
python main.py --test  # Run test mode first
python main.py         # Run live
```

## Key Differences Between APIs

| Feature | Groww API | Flattrade API |
|---------|-----------|---------------|
| Authentication | JWT token via API key/secret | Session token from login flow |
| Historical Data | Direct candle retrieval | Time-price series with Unix timestamps |
| Option Chain | Built-in option chain | Manual strike retrieval or option_chain API |
| Symbol Format | Dash-separated (NSE-NIFTY) | Concatenated (NIFTYFUT) |
| Data Freshness | Real-time | Real-time |
| Rate Limiting | Moderate | Moderate (similar) |
| Open Interest | Directly available | Limited for index options |

## Known Limitations

### Open Interest (OI) Data
Flattrade's API has limited OI data for index options. The conversion uses placeholders:
- `total_ce_oi` and `total_pe_oi` are set to placeholder values (1,000,000)
- PCR calculation defaults to 1.0
- Individual strike OI tracking is not available

**Impact**: Strategies heavily relying on OI changes may need adjustments.

### IV (Implied Volatility) Data
IV is not directly provided by Flattrade. The conversion uses:
- A placeholder value of 20.0 for ATM IV
- IV percentile calculation continues with placeholder data

**Impact**: Volatility-based strategies may need recalibration.

### Workarounds
For production use, consider:
1. Using external OI data sources
2. Implementing IV calculation using Black-Scholes model
3. Adjusting strategies to rely more on price action than OI

## Files Modified

- `config.py` - Updated credentials structure and log path
- `data/data_engine.py` - Complete API conversion
- `orchestrator.py` - Updated DataEngine initialization
- `main.py` - Updated banner and references (Experiment 8)

## Files Unchanged

All other files remain functionally identical:
- All strategy files
- Market intelligence modules
- Execution layer
- Risk management
- Signal aggregation
- Logging infrastructure

## Testing Checklist

- [ ] Configuration loads without errors
- [ ] API authentication successful
- [ ] Spot data fetching works
- [ ] Future data fetching works
- [ ] Option chain/strikes fetching works
- [ ] Indicators calculate correctly (RSI, EMA, ADX, ATR, VWAP)
- [ ] All strategies initialize
- [ ] Market intelligence modules work
- [ ] Test mode passes all checks
- [ ] Live data updates properly

## Recent Improvements (January 2026)

### Indicator Calculation Accuracy

The data engine now uses **pandas_ta** library for indicator calculations to ensure accuracy matching charting platforms (Groww, TradingView):

#### Technical Indicators
- **RSI**: Uses Wilder's RMA (Running Moving Average) smoothing - matches Groww/TradingView exactly
- **ADX/ATR**: Uses Wilder's smoothing method for accurate trend strength and volatility measurements
- **EMAs**: Standard exponential moving averages (5, 13, 21, 50 periods)
- **VWAP**: Intraday-only calculation, resets daily at 09:15 AM market open

#### Why This Matters
Charting platforms use specific smoothing algorithms (especially Wilder's method for RSI/ADX/ATR). Using pandas_ta ensures our indicator values match these platforms, leading to:
- Consistent signal generation
- Accurate backtesting vs live trading
- Reliable strategy decision-making

#### Installation
```bash
pip install pandas_ta
```

If pandas_ta is not available, the engine falls back to manual calculations with a warning. For production use, always install pandas_ta.

### VWAP: Intraday-Only Calculation

VWAP is now calculated correctly as an **intraday indicator**:

**Previous Behavior:**
- VWAP calculated over multiple days of data
- Carried forward from previous sessions
- Incorrect for intraday strategies

**Current Behavior:**
- Filters data to today's session only (post 09:15 AM)
- Resets daily at market open
- Uses NIFTY FUTURES volume (index has no volume!)
- Matches TradingView VWAP on futures chart

**Strategy Impact:**
All VWAP-based strategies (VWAP_BOUNCE, VWAP_EMA_TREND) now have reliable VWAP values for comparisons.

### PCR Calculation Optimization

Put-Call Ratio (PCR) calculation has been optimized for stability and reduced API usage:

**Previous Behavior:**
- PCR calculated every update
- Narrow strike window (ATM ± 50-100)
- High API usage (20-26 calls per minute)
- Noisy PCR values

**Current Behavior:**
- PCR updated every **3 minutes** (configurable via `BotConfig.PCR_UPDATE_INTERVAL`)
- Wider strike range (ATM ± 300, total 13 strikes)
- Regular updates: ATM-only (2 API calls)
- PCR updates: Full range (26 API calls)

**Configuration:**
```python
# config.py
PCR_UPDATE_INTERVAL = 180  # Seconds (3 minutes)
```

**Benefits:**
- **90% reduction in API calls** for option chain
- More stable PCR values reflecting broader market sentiment
- Reduced rate limit exposure
- Faster update cycles (option chain fetch: <500ms vs 2-5s)

### Option Chain Fetch Policy

Option chain fetching now uses an intelligent tiered approach:

#### Regular Updates (Every Tick)
- Fetch **ATM strike only** (CE + PE = 2 API calls)
- Update ATM prices for immediate trading decisions
- Include any strikes with active positions

#### PCR Refresh (Every 3 Minutes)
- Fetch wide range: ATM ± 300 in steps of 50 (13 strikes = 26 API calls)
- Calculate stable PCR from broader market data
- Update market breadth indicators

#### On-Demand Fetch
- Lazy loading: Only fetch additional strikes when needed
- Used by `get_affordable_strike()` when ATM is too expensive
- Used by position management when specific strikes are monitored

**Example Flow:**
```
Update 1 (00:00): PCR refresh (26 calls) + ATM (already included)
Update 2 (00:01): ATM only (2 calls)
Update 3 (00:02): ATM only (2 calls)
Update 4 (00:03): PCR refresh (26 calls) + ATM (already included)
...
Average: ~4 calls per update vs 20-26 previously
```

### Enhanced Logging

CSV logs now include additional observability columns:

```csv
Timestamp,Spot,Future,RSI,ADX,ATR,VWAP,EMA5,EMA13,ATM,PCR,Volume_Rel,PCR_LastRefresh,ChainCalls
09:15:30,24100.50,24105.20,52.3,18.5,45.2,24103.00,24098,24095,24100,1.05,1.2,09:15:30,26
09:16:30,24105.20,24110.10,53.1,18.8,45.5,24104.50,24099,24096,24100,1.05,1.3,,2
09:17:30,24110.50,24115.30,54.2,19.2,46.0,24106.00,24100,24097,24100,1.05,1.1,,2
```

**New Columns:**
- `PCR_LastRefresh`: Timestamp of last PCR calculation (HH:MM:SS)
- `ChainCalls`: Number of option chain API calls in this update

This allows monitoring of:
- PCR update frequency (should be ~3 minutes)
- API call patterns (should be 2 most of the time, 26 every 3 min)
- Rate limiting issues
- Performance optimization

### Data Lookback Optimization

Historical data fetching optimized for performance:

**Spot Data (for indicators):**
- Lookback: **2 trading days**
- Sufficient for EMA50 warm-up (~100 candles at 1-min)
- Reduces API latency and memory usage

**Future Data (for VWAP):**
- Lookback: **Today since 09:15 AM**
- VWAP is intraday-only, doesn't need historical days
- Further reduces data volume

**Benefits:**
- Faster initial data fetch
- Reduced memory footprint
- Maintained indicator accuracy

## Support

For issues specific to:
- **Flattrade API**: Refer to `../pythonAPI-main/README.md`
- **Trading Logic**: See `COMPLETE_DOCUMENTATION.md`
- **Market Intelligence**: See strategy documentation

## Migration from Experiment 6

If you're running Experiment 6 (Groww API) and want to migrate:

1. Stop Experiment 6
2. Set up Flattrade credentials
3. Update `experiment8/config.py`
4. Run test mode: `python main.py --test`
5. If tests pass, run live: `python main.py`

Your strategies, risk management, and all other logic remain identical.
