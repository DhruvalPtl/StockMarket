# @title V64 Data Recorder (Save All Data to CSV)
from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import datetime
import csv
import time
import sys
import os

# --- YOUR CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- CONFIGURATION ---
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"  # Verified Symbol
EXPIRY_DATE    = "2025-12-23"             # Verified Expiry
CSV_FILENAME   = "V64_Live_Data_Log.csv"

def initialize():
    try:
        print("🔌 Connecting to Groww...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ Connected.")
        return groww
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        sys.exit()

def get_futures_vwap(groww):
    """
    Fetches Futures candles to calculate Intraday VWAP & Volume.
    """
    try:
        end = datetime.datetime.now()
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        
        # Get 1-minute candles for precision
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        
        if not resp or 'candles' not in resp: return None, 0, 0

        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]

        # VWAP Calculation
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['vp'] = df['tp'] * df['volume']
        df['total_vp'] = df['vp'].cumsum()
        df['total_vol'] = df['volume'].cumsum()
        df['VWAP'] = df['total_vp'] / df['total_vol']
        
        latest = df.iloc[-1]
        return latest['close'], latest['VWAP'], latest['volume']
    except:
        return 0, 0, 0

def get_atm_chain_data(groww, spot_price):
    """
    Fetches the Option Chain and extracts ATM Data (OI, Greeks).
    """
    try:
        atm_strike = int(round(spot_price / 50) * 50)
        
        chain = groww.get_option_chain(
            exchange=groww.EXCHANGE_NSE,
            underlying="NIFTY",
            expiry_date=EXPIRY_DATE
        )
        
        if not chain or 'strikes' not in chain: return None
        
        # Extract Data for ATM Strike
        strike_data = chain['strikes'].get(str(atm_strike))
        if not strike_data: return None
        
        ce = strike_data.get("CE", {})
        pe = strike_data.get("PE", {})
        
        return {
            "strike": atm_strike,
            "ce_ltp": ce.get("ltp", 0),
            "ce_oi": ce.get("open_interest", 0),
            "ce_delta": ce.get("greeks", {}).get("delta", 0),
            "pe_ltp": pe.get("ltp", 0),
            "pe_oi": pe.get("open_interest", 0)
        }
    except:
        return None

def main():
    groww = initialize()
    
    # Check if file exists to write header
    file_exists = os.path.isfile(CSV_FILENAME)
    
    print(f"STARTING LOGGING TO: {CSV_FILENAME}")
    print("Press Ctrl+C to stop.\n")
    
    with open(CSV_FILENAME, "a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Timestamp", "Fut_Price", "Fut_VWAP", "Fut_Vol",
                "ATM_Strike", "CE_Price", "CE_OI", "CE_Delta",
                "PE_Price", "PE_OI", "Short_Covering_Signal"
            ])
            
        while True:
            try:
                # 1. Get Futures Data
                fut_price, fut_vwap, fut_vol = get_futures_vwap(groww)
                
                if fut_price == 0:
                    print("Waiting for Futures data...", end='\r')
                    time.sleep(2)
                    continue
                
                # 2. Get Option Chain Data
                opt_data = get_atm_chain_data(groww, fut_price)
                
                if opt_data:
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    
                    # Logic Check (For CSV)
                    signal = "WAIT"
                    if fut_price > fut_vwap: signal = "BULLISH_TREND"
                    if fut_price < fut_vwap: signal = "BEARISH_TREND"
                    
                    row = [
                        ts, fut_price, round(fut_vwap, 2), fut_vol,
                        opt_data['strike'], 
                        opt_data['ce_ltp'], opt_data['ce_oi'], opt_data['ce_delta'],
                        opt_data['pe_ltp'], opt_data['pe_oi'],
                        signal
                    ]
                    
                    writer.writerow(row)
                    f.flush() # Force save to disk immediately
                    
                    print(f"[{ts}] Saved: Fut {fut_price} | VWAP {round(fut_vwap, 2)} | CE OI {opt_data['ce_oi']}")
                
                time.sleep(5) # Log every 5 seconds
                
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    main()