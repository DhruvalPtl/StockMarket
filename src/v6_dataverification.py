import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys

# ==========================================
# ⚙️ STEP 1 CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# DATES: Fetch last 2 days to verify recent data
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=2)

# SYMBOLS (Check these on Groww App to ensure they are active!)
SPOT_SYMBOL = "NSE-NIFTY"                # For EMA & RSI
FUT_SYMBOL  = "NSE-NIFTY-30Dec25-FUT"    # For VWAP & Futures OI
TEST_OPT    = "NSE-NIFTY-23Dec25-26000-CE" # For Option Pricing & Option OI

class DataAuditor:
    def __init__(self):
        print("--- PART 1: DATA VERIFICATION ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
        except Exception as e:
            print(f"❌ Login Failed: {e}"); sys.exit()

    def fetch_raw(self, symbol, name):
        print(f"📥 Fetching {name} ({symbol})...")
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO" if "FUT" in symbol or "CE" in symbol or "PE" in symbol else "CASH", 
                symbol,
                START_DATE.strftime("%Y-%m-%d 09:15:00"), 
                END_DATE.strftime("%Y-%m-%d 15:30:00"), 
                "5minute"
            )
            
            if not resp or 'candles' not in resp or not resp['candles']:
                print(f"   ⚠️ WARNING: No data for {symbol}. Check Symbol Name/Expiry!")
                return None

            # Create DataFrame
            df = pd.DataFrame(resp['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            
            # 1. Clean Timestamp (Remove T)
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 2. Handle Missing OI (Spot has no OI, so fill with 0)
            if 'oi' in df.columns:
                df['oi'] = df['oi'].fillna(0)
            else:
                df['oi'] = 0
                
            return df
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def run(self):
        # 1. Fetch Independent Data Streams
        spot_df = self.fetch_raw(SPOT_SYMBOL, "SPOT")
        fut_df  = self.fetch_raw(FUT_SYMBOL, "FUTURES")
        opt_df  = self.fetch_raw(TEST_OPT, "OPTION (Test)")

        if spot_df is None or fut_df is None:
            print("❌ Critical Data Missing. Cannot proceed.")
            return

        # 2. Merge Dataframes by Time (Inner Join)
        # This ensures we only look at rows where we have data for ALL symbols
        print("🔄 Merging Data & Calculating Indicators...")
        
        merged = pd.merge(spot_df, fut_df, on='time', suffixes=('_SPOT', '_FUT'))
        
        if opt_df is not None:
            merged = pd.merge(merged, opt_df[['time', 'close', 'oi']], on='time', how='left')
            merged.rename(columns={'close': 'OPT_CLOSE', 'oi': 'OPT_OI'}, inplace=True)
        else:
            merged['OPT_CLOSE'] = 0
            merged['OPT_OI'] = 0

        # 3. Calculate Indicators (The logic you want to verify)
        
        # VWAP (Calculated on FUTURES because Spot has no real volume)
        merged['VWAP_FUT'] = (merged['volume_FUT'] * (merged['high_FUT'] + merged['low_FUT'] + merged['close_FUT']) / 3).cumsum() / merged['volume_FUT'].cumsum()
        
        # EMAs (Calculated on SPOT)
        merged['EMA5_SPOT'] = merged['close_SPOT'].ewm(span=5, adjust=False).mean()
        merged['EMA13_SPOT'] = merged['close_SPOT'].ewm(span=13, adjust=False).mean()
        
        # OI Change (Calculated on FUTURES)
        merged['OI_RAW'] = merged['oi_FUT']
        merged['OI_CHG'] = merged['oi_FUT'].diff().fillna(0)

        # 4. Save to CSV
        filename = "VERIFICATION_DATA.csv"
        
        # Select clean columns for easy reading
        final_df = merged[[
            'time', 
            'close_SPOT', 'EMA5_SPOT', 'EMA13_SPOT', 
            'close_FUT', 'VWAP_FUT', 'OI_RAW', 'OI_CHG',
            'OPT_CLOSE', 'OPT_OI'
        ]]
        
        final_df.to_csv(filename, index=False)
        print(f"\n✅ Data saved to {filename}")
        print("👉 Please open this file and compare 'close_SPOT' and 'OI_RAW' with your Groww App.")
        print("   - If OI_RAW is 0, the Futures Symbol is wrong.")
        print("   - If OPT_OI is 0, the Option Symbol is wrong.")

if __name__ == "__main__":
    DataAuditor().run()