# @title V67 Error Revealer
from growwapi import GrowwAPI
import datetime
import sys

# --- YOUR CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- THE SYMBOL THAT FAILED IN YOUR LOG ---
# The log shows Futures ~25977, so ATM Strike is 26000.
# The Trend was BEARISH, so it looked for PE.
FAILED_SYMBOL = "NSE-NIFTY-23Dec25-26000-PE" 

def test_specific_symbol():
    print(f"🔎 DIAGNOSING SYMBOL: {FAILED_SYMBOL}")
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        
        # Try to fetch 5-min candles (Same as V67)
        end = datetime.datetime.now()
        start = end - datetime.timedelta(minutes=30)
        
        print("   Attempting to fetch 5-min candles...")
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FAILED_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        
        if not resp:
            print("❌ ERROR: API returned Empty Response (None).")
            print("   -> Check if the Symbol spelling is 100% correct.")
            print("   -> Check if this Contract has expired.")
        elif 'candles' not in resp:
            print(f"❌ ERROR: Response missing 'candles' data.")
            print(f"   Raw Response: {resp}")
        elif len(resp['candles']) == 0:
            print("❌ ERROR: Symbol exists, but NO DATA returned (Empty List).")
            print("   -> Market might be closed or this strike is illiquid.")
        else:
            latest = resp['candles'][-1]
            print("✅ SUCCESS! Data Found:")
            print(f"   Price: {latest[4]}")
            print(f"   OI:    {latest[6] if len(latest)>6 else 'N/A'}")
            print("   -> The symbol works. The error was temporary?")

    except Exception as e:
        print(f"\n❌ CRITICAL EXCEPTION: {e}")
        print("   -> This is the error that V67 was hiding.")

if __name__ == "__main__":
    test_specific_symbol()