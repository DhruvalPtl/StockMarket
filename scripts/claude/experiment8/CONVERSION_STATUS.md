# Experiment 8 - Conversion Status

## ✅ COMPLETED

### 1. Configuration (config.py)
- ✅ Changed API credentials from Groww (API_KEY, API_SECRET) to Flattrade (USER_TOKEN, USER_ID)
- ✅ Updated log path to experiment8
- ✅ All other settings preserved (strategies, risk params, timeframes, etc.)

### 2. Documentation
- ✅ Created comprehensive README_FLATTRADE.md explaining:
  - API differences
  - Setup instructions
  - Symbol format changes
  - Known limitations (OI, IV data)
  - Migration guide

### 3. Main Entry Point (main.py)
- ✅ Updated banner to show "Experiment 8"
- ✅ Updated docstring to mention Flattrade API

### 4. Orchestrator (orchestrator.py)
- ✅ Updated DataEngine initialization to use USER_TOKEN and USER_ID instead of API_KEY and API_SECRET
- ✅ Updated banner message

### 5. Data Engine (data/data_engine.py) - PARTIAL
- ✅ Updated imports to use Flattrade API (NorenApiPy)
- ✅ Added pythonAPI-main to sys.path
- ✅ Updated __init__ to accept user_token and user_id
- ✅ Added timeframe_map for Flattrade interval format
- ✅ Added token_cache dictionary
- ✅ Updated _connect() method to use Flattrade authentication
- ✅ Added _get_token() helper method for symbol lookup
- ⚠️  **INCOMPLETE**: Data fetching methods need conversion

### 6. Git Configuration
- ✅ Created .gitignore to exclude log files and cache
- ✅ Removed log directory from git tracking

## ⚠️ NEEDS COMPLETION

### Data Engine Data Fetching Methods

The following methods in `data/data_engine.py` still need to be converted from Groww API to Flattrade API:

#### 1. `_fetch_spot_data()` (Lines ~368-425)
**Current**: Uses `groww.get_historical_candles()`  
**Needs**:  
```python
# Get Nifty 50 token
token = self._get_token('NSE', 'Nifty 50') or '26000'

# Use get_time_price_series
ret = self.api.get_time_price_series(
    exchange='NSE',
    token=token,
    starttime=start_time_unix,
    endtime=end_time_unix,
    interval=self.timeframe_map[self.timeframe]
)

# Parse response:
# Flattrade returns list of dicts with: stat, time, into, inth, intl, intc, intvwap, intv
```

#### 2. `_fetch_future_data()` (Lines ~427-510)
**Current**: Uses `groww.get_historical_candles()`  
**Needs**:
```python
# Build future symbol from expiry date
exp_date = datetime.strptime(self.future_expiry, "%Y-%m-%d")
fut_symbol = f"NIFTY{exp_date.strftime('%d%b%y').upper()}FUT"

# Get token
token = self._get_token('NFO', fut_symbol)

# Fetch data
ret = self.api.get_time_price_series(
    exchange='NFO',
    token=token,
    starttime=start_time_unix,
    endtime=end_time_unix,
    interval=self.timeframe_map[self.timeframe]
)
```

#### 3. `_fetch_option_chain()` (Lines ~512-640)
**Current**: Uses Groww's option chain endpoint  
**Needs**: Two approaches:

**Approach A**: Use Flattrade's get_option_chain (if available)
```python
exp_date = datetime.strptime(self.option_expiry, "%Y-%m-%d")
exp_str = exp_date.strftime('%d%b%y').upper()
fut_symbol = f"NIFTY{exp_str}FUT"

ret = self.api.get_option_chain(
    exchange='NFO',
    tradingsymbol=fut_symbol,
    strikeprice=float(self.atm_strike),
    count=5
)
```

**Approach B**: Manual strike fetching (fallback)
```python
for strike in range(atm_strike - 200, atm_strike + 250, 50):
    ce_symbol = f"NIFTY{exp_str}{strike}CE"
    pe_symbol = f"NIFTY{exp_str}{strike}PE"
    
    ce_token = self._get_token('NFO', ce_symbol)
    pe_token = self._get_token('NFO', pe_symbol)
    
    if ce_token:
        ce_quote = self.api.get_quotes(exchange='NFO', token=ce_token)
        # Extract LTP from ce_quote
    
    if pe_token:
        pe_quote = self.api.get_quotes(exchange='NFO', token=pe_symbol)
        # Extract LTP from pe_quote
```

**Note**: Flattrade has limited OI data for index options. Use placeholders or external sources.

### Response Format Conversion

#### Groww Format:
```python
{
    'candles': [
        [timestamp, open, high, low, close, volume],
        ...
    ]
}
```

#### Flattrade Format:
```python
[
    {
        'stat': 'Ok',
        'time': 'DD-MM-YYYY HH:MM:SS',
        'into': 'open',
        'inth': 'high',
        'intl': 'low',
        'intc': 'close',
        'intvwap': 'vwap',
        'intv': 'volume',
        'intoi': 'oi_change',
        'oi': 'oi'
    },
    ...
]
```

## 📋 TODO LIST

1. **Complete Data Engine Conversion**
   - [ ] Convert `_fetch_spot_data()` to use Flattrade API
   - [ ] Convert `_fetch_future_data()` to use Flattrade API
   - [ ] Convert `_fetch_option_chain()` to use Flattrade API
   - [ ] Test data fetching with actual Flattrade credentials

2. **Handle Limitations**
   - [ ] Decide on approach for OI data (placeholders vs external source)
   - [ ] Decide on approach for IV data (calculate or placeholder)

3. **Testing**
   - [ ] Test with actual Flattrade credentials
   - [ ] Run `python main.py --test` to verify all systems
   - [ ] Check data quality and indicator calculations
   - [ ] Verify option chain loading

4. **Update Requirements**
   - [ ] Create/update requirements.txt if needed
   - [ ] Document any additional dependencies

## 🔧 QUICK FIX GUIDE

To complete the conversion quickly:

1. Open `data/data_engine.py`
2. Find line ~368 (`_fetch_spot_data`)
3. Replace the Groww API call with Flattrade equivalent (see above)
4. Find line ~427 (`_fetch_future_data`)
5. Replace the Groww API call with Flattrade equivalent
6. Find line ~512 (`_fetch_option_chain`)
7. Implement option chain fetching using Flattrade API

## 🧪 TESTING

After completing the above:

```bash
cd /path/to/experiment8

# Set credentials in config.py first!
# USER_TOKEN = "your_flattrade_session_token"
# USER_ID = "your_user_id"

# Run test mode
python main.py --test

# If tests pass, run live
python main.py
```

## 📚 REFERENCE FILES

- Flattrade API examples: `../pythonAPI-main/example_market.py`
- Flattrade API helper: `../pythonAPI-main/api_helper.py`
- Original Groww implementation: `../experiment6/data/data_engine.py`

## ⚡ ESTIMATED TIME

- Complete data fetching methods: 1-2 hours
- Testing with real credentials: 30 minutes
- Total: 1.5-2.5 hours
