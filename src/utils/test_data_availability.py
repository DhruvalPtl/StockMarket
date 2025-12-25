import pandas as pd
import time
from datetime import timedelta
from growwapi import GrowwAPI

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM1Njg0NzYsImlhdCI6MTc2NTE2ODQ3NiwibmJmIjoxNzY1MTY4NDc2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhMTg3NDVhMy1hN2M1LTRlOTQtODE1MS1lZjUxZDQ5OGE2Y2RcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjBlOWMyYWZmLTM0NzktNDUyMi1iODE4LTczNTZlMzFkYmY1Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjNkMWQ6MWZmMDo1YWFjOjYwNTYsMTcyLjcxLjE5OC4xOSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1MzU2ODQ3NjQzNn0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.VuAMgqoC3e32gduObByNz97jFfG-ikXoREum26XPkvyMpj9JgCedXBI81jxGTPTrZD9i1wIL0s38LPd9vc9ApA"
API_SECRET = "xy0sbQ4r*!HN3&&UKc9vpwti4xx8PR)("

# --- CONFIGURATION ---
SPOT_FILE = "Final_nifty_spot_1minute_fixed_trimmed.csv" 
OUTPUT_FILE = "nifty_options_2020_2025_confirmed.csv"

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"CRITICAL: Auth failed. Check keys. Error: {e}")
        exit()

# --- 1. SMART EXPIRY CALCULATOR ---
def get_target_expiry_date(date_obj):
    """
    Calculates expiry date.
    - Before Sep 2025: Thursday
    - After Sep 2025: Tuesday
    """
    switch_date = pd.Timestamp("2025-09-01")
    target_day = 1 if date_obj >= switch_date else 3 # 1=Tue, 3=Thu
    
    days_ahead = target_day - date_obj.weekday()
    if days_ahead < 0: 
        days_ahead += 7
        
    return date_obj + timedelta(days=days_ahead)

# --- STEP 1: LOAD SPOT DATA ---
print(f"Loading {SPOT_FILE}...")
try:
    df_spot = pd.read_csv(SPOT_FILE)
    if isinstance(df_spot['timestamp'].iloc[0], str):
        df_spot['timestamp'] = pd.to_datetime(df_spot['timestamp'])
    else:
        df_spot['timestamp'] = pd.to_datetime(df_spot['timestamp'], unit='s')
    df_spot.sort_values('timestamp', inplace=True)
except FileNotFoundError:
    print(f"Error: {SPOT_FILE} not found.")
    exit()

print(f"Loaded {len(df_spot)} rows.")

# Calculate ATM
df_spot['atm_strike'] = (df_spot['close'] / 50).round() * 50

# Calculate Expiry Date
print("Calculating Expiries...")
df_spot['expiry_dt'] = df_spot['timestamp'].apply(get_target_expiry_date)
# CONFIRMED FORMAT: 09Jan20 (%d%b%y)
df_spot['expiry_str'] = df_spot['expiry_dt'].dt.strftime("%d%b%y")

# --- STEP 2: DOWNLOAD BATCH HISTORY ---
groww = auth()
option_cache = {} 
grouped = df_spot.groupby('expiry_str')

print(f"\n--- Starting Download for {len(grouped)} Weeks ---")

for expiry_str, group in grouped:
    # 1. Identify Strikes (ATM, ITM, OTM)
    atm_strikes = group['atm_strike'].unique().astype(int)
    strikes_to_fetch = set()
    for k in atm_strikes:
        strikes_to_fetch.add(k)       # ATM
        strikes_to_fetch.add(k - 50)  # ITM Call / OTM Put
        strikes_to_fetch.add(k + 50)  # OTM Call / ITM Put
    strikes_to_fetch = sorted(list(strikes_to_fetch))
    
    # 2. Setup Dates (Handle Holidays)
    primary_dt = group['expiry_dt'].iloc[0]
    backup_dt = primary_dt - timedelta(days=1) # Previous day (Wed/Mon)
    
    # Formats
    fmt_primary = primary_dt.strftime("%d%b%y") # e.g. 09Jan20
    fmt_backup = backup_dt.strftime("%d%b%y")   # e.g. 08Jan20
    
    # Optimization: Check if Primary works for one symbol. If not, switch whole batch to Backup.
    # This saves 50% API calls on holiday weeks.
    active_fmt = fmt_primary
    
    # Quick Check on first strike to determine active format
    test_sym = f"NSE-NIFTY-{fmt_primary}-{strikes_to_fetch[0]}-CE"
    try:
        # Check just 1 day to see if symbol exists
        check_start = group['timestamp'].min().strftime("%Y-%m-%d %H:%M:%S")
        check_end = (group['timestamp'].min() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        resp = groww.get_historical_candles(
             exchange="NSE", segment="FNO", groww_symbol=test_sym,
             start_time=check_start, end_time=check_end, candle_interval="1minute"
        )
        if not (resp and "candles" in resp and len(resp["candles"]) > 0):
            # Primary failed, assume Holiday, switch to Backup
            active_fmt = fmt_backup
    except:
        active_fmt = fmt_backup # Error often means invalid symbol -> Holiday
        
    print(f"Week {expiry_str} | Using: {active_fmt} | Strikes: {len(strikes_to_fetch)}")
    
    # 3. Download Loop
    start_dt = group['timestamp'].min().strftime("%Y-%m-%d %H:%M:%S")
    end_dt = group['timestamp'].max().strftime("%Y-%m-%d %H:%M:%S")
    
    for strike in strikes_to_fetch:
        for opt_type in ['CE', 'PE']:
            
            # Construct Symbol with the DETECTED valid date
            sym = f"NSE-NIFTY-{active_fmt}-{strike}-{opt_type}"
            
            if sym in option_cache: continue
            
            try:
                # Fetch full week
                resp = groww.get_historical_candles(
                    exchange="NSE", segment="FNO", groww_symbol=sym,
                    start_time=start_dt, end_time=end_dt, candle_interval="1minute"
                )
                
                if resp and "candles" in resp and len(resp["candles"]) > 0:
                    df = pd.DataFrame(resp["candles"], columns=['ts', 'o', 'h', 'l', 'close', 'v'])
                    df['timestamp'] = pd.to_datetime(df['ts'], unit='s')
                    df.set_index('timestamp', inplace=True)
                    df = df[~df.index.duplicated(keep='first')]
                    option_cache[sym] = df
            except Exception as e:
                # print(f"Error fetching {sym}: {e}")
                pass

    # --- STEP 3: STITCH & SAVE ---
    week_rows = []
    
    for index, row in group.iterrows():
        ts = row['timestamp']
        atm = int(row['atm_strike'])
        
        # Lookup function using the ACTIVE format
        def lookup(s, t):
            k = f"NSE-NIFTY-{active_fmt}-{s}-{t}"
            if k in option_cache and ts in option_cache[k].index:
                return option_cache[k].loc[ts]['close']
            return None

        week_rows.append({
            "timestamp": ts,
            "nifty_ltp": row['close'],
            "expiry": expiry_str,
            "active_expiry_date": active_fmt, # Save which date worked (Thu or Wed)
            "atm_strike": atm,
            "atm_ce": lookup(atm, "CE"),
            "atm_pe": lookup(atm, "PE"),
            "itm_ce": lookup(atm - 50, "CE"),
            "itm_pe": lookup(atm + 50, "PE")
        })
        
    df_week = pd.DataFrame(week_rows)
    # Save incrementally
    header = not pd.io.common.file_exists(OUTPUT_FILE)
    df_week.to_csv(OUTPUT_FILE, mode='a', header=header, index=False)
    
    option_cache.clear()

print(f"\n✅ DONE! Data saved to {OUTPUT_FILE}")