# @title OI Data Finder (5-Minute Check)
from growwapi import GrowwAPI
import datetime
import sys

# --- YOUR CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- USE THE OPTION SYMBOL YOU FOUND ---
# Make sure this is an active strike (Near ATM)
OPTION_SYMBOL = "NSE-NIFTY-23Dec25-26000-CE" 

def check_oi_specifically():
    print(f"🔎 SEARCHING FOR OI DATA IN {OPTION_SYMBOL}...")
    
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        
        # WE REQUEST 5-MINUTE CANDLES (Because OI lives here)
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=OPTION_SYMBOL,
            start_time=(datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"  # <--- THIS IS THE SECRET
        )
        
        if resp and 'candles' in resp and len(resp['candles']) > 0:
            # Get the last candle
            latest = resp['candles'][-1]
            
            # Index 0=Time, 1=Open, 2=High, 3=Low, 4=Close, 5=Volume, 6=OI
            price = latest[4]
            volume = latest[5]
            
            # CHECK INDEX 6 FOR OI
            if len(latest) > 6:
                oi_value = latest[6]
                print(f"\n✅ FOUND IT!")
                print(f"   Time:   {latest[0]}")
                print(f"   Price:  {price}")
                print(f"   Volume: {volume}")
                print(f"   OI:     {oi_value}  <--- HERE IS THE DATA")
            else:
                print("\n❌ DATA ARRIVED, BUT OI COLUMN IS MISSING.")
                print(f"   Raw Data: {latest}")
                
        else:
            print("\n❌ NO DATA RECEIVED. Check Symbol spelling.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    check_oi_specifically()