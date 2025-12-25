import pandas as pd
import numpy as np
import time
from datetime import timedelta
from growwapi import GrowwAPI

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM1Njg0NzYsImlhdCI6MTc2NTE2ODQ3NiwibmJmIjoxNzY1MTY4NDc2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhMTg3NDVhMy1hN2M1LTRlOTQtODE1MS1lZjUxZDQ5OGE2Y2RcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjBlOWMyYWZmLTM0NzktNDUyMi1iODE4LTczNTZlMzFkYmY1Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjNkMWQ6MWZmMDo1YWFjOjYwNTYsMTcyLjcxLjE5OC4xOSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1MzU2ODQ3NjQzNn0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.VuAMgqoC3e32gduObByNz97jFfG-ikXoREum26XPkvyMpj9JgCedXBI81jxGTPTrZD9i1wIL0s38LPd9vc9ApA"
API_SECRET = "xy0sbQ4r*!HN3&&UKc9vpwti4xx8PR)("

# --- CONFIGURATION ---
# Use your large 2020-2025 Spot File here
SPOT_FILE = "Final_nifty_spot_1minute_fixed_trimmed.csv" 
OUTPUT_FILE = "nifty_options_2020_2025.csv"

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"Auth failed: {e}")
        exit()

# --- 1. SMART EXPIRY CALCULATOR ---
def get_next_expiry_date(date_obj):
    """
    Finds the next Thursday for any given date (2020-2025).
    """
    # weekday(): 0=Mon, ... 3=Thu, ... 6=Sun
    days_ahead = 3 - date_obj.weekday()
    if days_ahead < 0: 
        # If it's Fri/Sat/Sun, go to next week's Thursday
        days_ahead += 7
    
    # If it is Thursday (days_ahead=0), it is the expiry day!
    next_thursday = date_obj + timedelta(days=days_ahead)
    return next_thursday

# --- STEP 1: LOAD & PROCESS SPOT DATA ---
print(f"Loading {SPOT_FILE}...")
try:
    # Assuming your file has 'timestamp' and 'close'
    df_spot = pd.read_csv(SPOT_FILE)
    
    # Auto-detect timestamp format
    if isinstance(df_spot['timestamp'].iloc[0], str):
        df_spot['timestamp'] = pd.to_datetime(df_spot['timestamp'])
    else:
        df_spot['timestamp'] = pd.to_datetime(df_spot['timestamp'], unit='s')
        
    # Sort just in case
    df_spot.sort_values('timestamp', inplace=True)
    
except FileNotFoundError:
    print(f"Error: {SPOT_FILE} not found. Please put your 2020 file in the folder.")
    exit()

print(f"Loaded {len(df_spot)} rows from {df_spot['timestamp'].min()} to {df_spot['timestamp'].max()}")

# 1. Calculate ATM Strike
print("Calculating ATM Strikes...")
df_spot['atm_strike'] = (df_spot['close'] / 50).round() * 50

# 2. Generate Expiry for 5 Years of Data
print("Generating Weekly Expiry Dates (This may take a moment)...")
df_spot['expiry_dt'] = df_spot['timestamp'].apply(get_next_expiry_date)

# Format as string for grouping: "13Nov25"
df_spot['expiry_str'] = df_spot['expiry_dt'].dt.strftime("%d%b%y")

# --- STEP 2: DOWNLOAD BATCH HISTORY ---
groww = auth()
option_cache = {} 
grouped = df_spot.groupby('expiry_str')

print(f"\n--- Found {len(grouped)} Expiry Weeks. Starting Download... ---")

for expiry_str, group in grouped:
    # Get the ATM strikes touched during this specific week
    atm_strikes = group['atm_strike'].unique().astype(int)
    
    # EXPAND LIST: Add ITM and OTM (ATM-50, ATM, ATM+50)
    strikes_to_fetch = set()
    for k in atm_strikes:
        strikes_to_fetch.add(k - 50) # ITM Call / OTM Put
        strikes_to_fetch.add(k)      # ATM
        strikes_to_fetch.add(k + 50) # OTM Call / ITM Put
    
    strikes_to_fetch = sorted(list(strikes_to_fetch))
    
    print(f"\nProcessing Week: {expiry_str} | Strikes needed: {len(strikes_to_fetch)}")
    
    # Time window for this week
    start_dt = group['timestamp'].min()
    end_dt = group['timestamp'].max()
    
    # Handle Holidays: We calculated Thursday, but what if Thursday was a holiday?
    # We will try Thursday symbol first. If fail, try Wednesday.
    thursday_dt = group['expiry_dt'].iloc[0]
    wednesday_dt = thursday_dt - timedelta(days=1)
    
    # Formats to try: [Thu_Weekly, Thu_Monthly, Wed_Weekly]
    # Note: Monthly format (NOV20) usually applies to the last Thu of month. 
    # For automation, we will try the explicit date format first as it covers 90% cases.
    
    fmt_thu = thursday_dt.strftime("%d%b%y") # e.g. 13Nov20
    fmt_wed = wednesday_dt.strftime("%d%b%y") # e.g. 12Nov20
    
    for strike in strikes_to_fetch:
        for opt_type in ['CE', 'PE']:
            
            # --- SMART HUNT LOGIC ---
            found_symbol = None
            
            # Try Thursday -> If Fail -> Try Wednesday (Holiday)
            for fmt in [fmt_thu, fmt_wed]:
                # Construct Symbol
                # Case Sensitive Check: Try "09JAN20" (Upper) if "09Jan20" fails? 
                # Groww usually uses Title case (09Jan20) for weekly.
                
                sym = f"NSE-NIFTY-{fmt}-{strike}-{opt_type}"
                
                if sym in option_cache:
                    found_symbol = sym
                    break
                
                # Fetch
                try:
                    # print(f"  Checking {sym}...", end="")
                    resp = groww.get_historical_candles(
                        exchange="NSE", segment="FNO", groww_symbol=sym,
                        start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        candle_interval="1minute"
                    )
                    
                    if resp and "candles" in resp and len(resp["candles"]) > 0:
                        # SUCCESS
                        # print(" Found!")
                        temp_df = pd.DataFrame(resp["candles"])
                        # Clean up
                        if len(temp_df.columns) >= 5:
                            temp_df.rename(columns={0: "timestamp", 4: "close"}, inplace=True)
                        
                        # Timestamp fix
                        if isinstance(temp_df["timestamp"].iloc[0], str):
                            temp_df["timestamp"] = pd.to_datetime(temp_df["timestamp"])
                        else:
                            temp_df["timestamp"] = pd.to_datetime(temp_df["timestamp"], unit='s')
                        
                        temp_df.set_index("timestamp", inplace=True)
                        temp_df = temp_df[~temp_df.index.duplicated(keep='first')]
                        
                        option_cache[sym] = temp_df
                        found_symbol = sym
                        break # Stop trying dates
                        
                except Exception:
                    pass
            
            if not found_symbol:
                # print(f"  ❌ No Data for Strike {strike} {opt_type} (tried {fmt_thu}/{fmt_wed})")
                pass

    # --- MEMORY MANAGEMENT ---
    # If option_cache gets too big (5 years data!), Python will crash.
    # We must Stitch & Save incrementally, then clear cache.
    
    print("  > Stitching & Saving this week...")
    week_rows = []
    
    for index, row in group.iterrows():
        ts = row['timestamp']
        atm = int(row['atm_strike'])
        
        # We need ATM, ATM-50, ATM+50
        row_data = {
            "timestamp": ts,
            "nifty_ltp": row['close'],
            "atm_strike": atm,
            "expiry": expiry_str
        }
        
        # Helper to find price in cache
        def get_price(s, t): # strike, type
            # Try to find the symbol we successfully downloaded for this strike
            # We look in cache keys
            for fmt in [fmt_thu, fmt_wed]:
                key = f"NSE-NIFTY-{fmt}-{s}-{t}"
                if key in option_cache:
                    try:
                        return option_cache[key].loc[ts]['close']
                    except KeyError:
                        return None
            return None

        # ATM
        row_data["atm_ce"] = get_price(atm, "CE")
        row_data["atm_pe"] = get_price(atm, "PE")
        
        # ITM Call (Strike - 50)
        row_data["itm_ce"] = get_price(atm - 50, "CE")
        
        # ITM Put (Strike + 50)
        row_data["itm_pe"] = get_price(atm + 50, "PE")
        
        week_rows.append(row_data)

    # Append to CSV immediately
    df_week = pd.DataFrame(week_rows)
    # If file doesn't exist, write header. If exists, append.
    header_mode = not pd.io.common.file_exists(OUTPUT_FILE)
    df_week.to_csv(OUTPUT_FILE, mode='a', header=header_mode, index=False)
    
    print(f"  > Saved {len(df_week)} rows. Clearing Cache.")
    option_cache = {} # Free up RAM

print(f"\n✅ COMPLETE! All data saved to {OUTPUT_FILE}")