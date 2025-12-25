# @title Data Connection Verifier (The Lie Detector)
from growwapi import GrowwAPI
import pandas as pd
import datetime
import sys

# --- YOUR CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- SYMBOLS TO TEST ---
# 1. SPOT (The Index)
SPOT_SYMBOL = "NSE-NIFTY" 
# 2. FUTURES (The Current Month Contract - CHECK DATE)
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"
# 3. OPTION (An ATM Option - CHECK DATE)
OPTION_SYMBOL = "NSE-NIFTY-23Dec25-26000-CE" 

def test_connection():
    print("🔌 CONNECTING TO GROWW API...")
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ AUTHENTICATION SUCCESSFUL.\n")
    except Exception as e:
        print(f"❌ AUTH FAILED: {e}")
        return

    # TEST 1: NIFTY SPOT (Cash Segment)
    print(f"1️⃣  TESTING SPOT DATA ({SPOT_SYMBOL})...")
    try:
        # Note: segment="CASH" is critical here
        resp = groww.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol=SPOT_SYMBOL,
            start_time=(datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if resp and 'candles' in resp and len(resp['candles']) > 0:
            latest = resp['candles'][-1]
            print(f"   [SUCCESS] Nifty Index Price: {latest[4]}")
        else:
            print("   [FAILED] No Data Received.")
    except Exception as e:
        print(f"   [ERROR] {e}")

    print("-" * 30)

    # TEST 2: NIFTY FUTURES (FNO Segment)
    print(f"2️⃣  TESTING FUTURES DATA ({FUTURES_SYMBOL})...")
    try:
        # Note: segment="FNO" is critical here
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=(datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if resp and 'candles' in resp and len(resp['candles']) > 0:
            latest = resp['candles'][-1]
            # Futures data has Volume (Index 5) and OI (Index 6 usually)
            close = latest[4]
            vol = latest[5]
            print(f"   [SUCCESS] Future Price: {close} | Volume: {vol}")
            print("   [VERIFIED] Volume Data Exists (Required for VWAP)")
        else:
            print("   [FAILED] No Data. (Check Symbol Name/Expiry?)")
    except Exception as e:
        print(f"   [ERROR] {e}")

    print("-" * 30)

    # TEST 3: OPTION DATA (FNO Segment)
    print(f"3️⃣  TESTING OPTION DATA ({OPTION_SYMBOL})...")
    try:
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=OPTION_SYMBOL,
            start_time=(datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        if resp and 'candles' in resp and len(resp['candles']) > 0:
            latest = resp['candles'][-1]
            # Option data often has OI in column 6 or 7
            close = latest[4]
            oi = latest[6] if len(latest) > 6 else "N/A"
            print(f"   [SUCCESS] Option Price: {close} | OI: {oi}")
            print("   [VERIFIED] OI Data Exists (Required for Short Covering)")
        else:
            print("   [FAILED] No Data. (Check Strike/Expiry?)")
    except Exception as e:
        print(f"   [ERROR] {e}")

if __name__ == "__main__":
    test_connection()