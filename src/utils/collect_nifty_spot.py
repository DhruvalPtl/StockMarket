import time
import pandas as pd
from datetime import timedelta
from growwapi import GrowwAPI

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"Auth failed: {e}")
        exit()

groww = auth()
print("Logged into Groww!")

# --- CONFIGURATION ---
# The new method requires these specific strings
SYMBOL = "NSE-NIFTY" 
EXCHANGE = "NSE"          # Passed as string
SEGMENT = "CASH"       # Passed as string ("INDICES" for Nifty 50, "CASH" for stocks)
INTERVAL = "1minute"           # Passed as string (e.g., "1m", "5m", "15m")

# --- CHUNKING LOGIC ---
total_days = 30
chunk_size_days = 5
end_date = pd.Timestamp.now()
start_date = end_date - timedelta(days=total_days)

all_candles = []
current_start = start_date

print(f"Starting batched download for {SYMBOL} ({SEGMENT})...")

while current_start < end_date:
    current_end = current_start + timedelta(days=chunk_size_days)
    if current_end > end_date:
        current_end = end_date
    
    # Format dates to string as required by signature
    s_str = current_start.strftime("%Y-%m-%d %H:%M:%S")
    e_str = current_end.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Fetching: {s_str} -> {e_str}")
    
    try:
        # UPDATED CALL MATCHING YOUR SIGNATURE
        resp = groww.get_historical_candles(
            exchange=EXCHANGE,
            segment=SEGMENT,
            groww_symbol=SYMBOL,
            start_time=s_str,
            end_time=e_str,
            candle_interval=INTERVAL
        )
        
        # Parse response
        if resp and "candles" in resp and resp["candles"]:
            chunk_data = resp["candles"]
            all_candles.extend(chunk_data)
            print(f"  > Success: {len(chunk_data)} candles.")
        else:
            # Sometimes API returns empty or wrapped data, print to debug if needed
            print(f"  > No data/Empty response. (Check if Market was open)")
            
    except Exception as e:
        print(f"  > Error: {e}")

    current_start = current_end
    time.sleep(0.5) # Rate limit protection

# --- SAVE TO CSV ---
# --- SAVE TO CSV ---
if all_candles:
    # 1. Create DataFrame
    df = pd.DataFrame(all_candles)
    
    # 2. Rename Columns (Handle optional 7th column)
    base_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    rename_map = {i: col for i, col in enumerate(base_cols)}
    df.rename(columns=rename_map, inplace=True)
    
    if len(df.columns) > 6:
        df.rename(columns={6: "open_interest"}, inplace=True)
    
    # 3. ROBUST TIMESTAMP FIX
    # Check the first value to decide how to convert
    first_ts = df["timestamp"].iloc[0]
    
    if isinstance(first_ts, str):
        # Case A: API returns strings like '2025-11-07T13:43:00'
        # Do NOT use unit='s' here.
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    else:
        # Case B: API returns numbers (Epoch seconds) like 1735660000
        # MUST use unit='s' here.
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')
    
    # 4. Clean & Save
    df.sort_values("timestamp", inplace=True)
    df.drop_duplicates(subset="timestamp", inplace=True)
    
    filename = "nifty_spot_1m.csv"
    df.to_csv(filename, index=False)
    print(f"\nDONE! Saved {len(df)} candles to {filename}")
    print("First 5 rows:")
    print(df.head())
else:
    print("\nFAILED: No data collected.")