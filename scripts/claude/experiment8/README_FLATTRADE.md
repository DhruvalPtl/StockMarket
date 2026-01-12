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
