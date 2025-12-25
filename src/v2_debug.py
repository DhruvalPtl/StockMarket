import pandas as pd
from growwapi import GrowwAPI
import datetime

# --- DEBUG CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef" # Paste Secret Here

# We test TWO symbols to show you the difference
# 1. The Index (Has Price, NO OI)
INDEX_SYMBOL = "NSE-NIFTY" 
# 2. The Future (Has Price AND OI) -> CHANGE THIS to a valid active future if needed
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 

def test_connection():
    print("\n--- 1. TESTING LOGIN ---")
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ Login Success! Token generated.")
        return groww
    except Exception as e:
        print(f"❌ Login Failed: {e}")
        return None

def check_data(groww, symbol):
    print(f"\n--- 2. FETCHING DATA FOR: {symbol} ---")
    
    # Fetch last 5 days of 5-minute candles
    end = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        response = groww.get_historical_candles(
            exchange="NSE",
            segment="FNO" if "FUT" in symbol or "CE" in symbol else "CASH",
            groww_symbol=symbol,
            start_time=start,
            end_time=end,
            candle_interval="5minute"
        )
        
        # Check 1: Did we get a response?
        if not response:
            print("❌ Error: Empty Response from API (Possible Rate Limit or Network Issue)")
            return

        # Check 2: Are there candles?
        if 'candles' not in response or len(response['candles']) == 0:
            print(f"⚠️ Warning: No candles found for {symbol}. Check if symbol is correct/active.")
            return

        # Check 3: Data Quality Analysis
        candles = response['candles']
        # Format: [time, open, high, low, close, volume, oi]
        df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        print(f"✅ Success! Fetched {len(df)} candles.")
        print("Sample Data (Last 3 rows):")
        print(df.tail(3)[['time', 'close', 'volume', 'oi']])
        
        # Check 4: THE TRUTH SERUM CHECK (Open Interest)
        oi_sample = df['oi'].iloc[-1]
        if pd.isna(oi_sample) or oi_sample is None:
            print(f"\n❌ CRITICAL: 'oi' is NONE for {symbol}.")
            print("   -> Reason: Spot Indices (Nifty 50) do NOT have Open Interest.")
            print("   -> Fix: Use a FUTURES or OPTIONS symbol for your Strategy.")
        else:
            print(f"\n✅ GREAT: 'oi' data exists ({oi_sample}). This symbol is valid for V2 Algo.")

    except Exception as e:
        print(f"❌ Crash during fetch: {e}")

# --- RUN DIAGNOSIS ---
api = test_connection()
if api:
    # Test 1: The one that failed before (Index)
    check_data(api, INDEX_SYMBOL)
    
    # Test 2: The one that should work (Futures)
    check_data(api, FUTURES_SYMBOL)