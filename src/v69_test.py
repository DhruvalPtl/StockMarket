# @title V69 - The Diagnostic Sniper (Find the Broken Link)
from growwapi import GrowwAPI
import pandas as pd
import datetime
import time
import csv
import traceback
import sys
import os
import pytz

# --- 🔐 CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- ⚙️ CONFIGURATION ---
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 
EXPIRY_DATE    = "2025-12-23" # <--- Double check this on Groww!
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = "V69_Diagnostic_Log.csv"

def initialize():
    try:
        print(f"[{datetime.datetime.now(IST).strftime('%H:%M:%S')}] 🔌 Connecting...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ Connection Verified.")
        return groww
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit()

def diagnostic_run(groww):
    print("\n" + "="*40)
    print(f"🔍 SYSTEM HEALTH CHECK: {datetime.datetime.now(IST).strftime('%H:%M:%S')}")
    print("="*40)
    
    data_found = {}

    # --- 1. TEST FUTURES (TREND) ---
    try:
        print("📡 1/3: Checking Nifty Futures...")
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=30)
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if resp and 'candles' in resp and len(resp['candles']) > 0:
            candles = resp['candles']
            cols_count = len(candles[0])
            ltp = candles[-1][4]
            print(f"   ✅ SUCCESS: Futures LTP is {ltp} ({cols_count} columns found)")
            data_found['fut_ltp'] = ltp
        else:
            print(f"   ❌ FAILED: Futures response empty. Resp: {resp}")
    except Exception as e:
        print(f"   ❌ ERROR in Futures: {e}")

    # --- 2. TEST OPTION CHAIN (SCANNER) ---
    if 'fut_ltp' in data_found:
        try:
            print("🔗 2/3: Checking Option Chain...")
            atm_strike = int(round(data_found['fut_ltp'] / 50) * 50)
            print(f"   (Using ATM Strike: {atm_strike})")
            
            chain = groww.get_option_chain(exchange=groww.EXCHANGE_NSE,underlying="NIFTY", expiry_date=EXPIRY_DATE)
            if chain and 'strikes' in chain:
                strike_data = chain['strikes'].get(str(atm_strike))
                if strike_data:
                    ce_sym = strike_data.get('CE', {}).get('trading_symbol', 'N/A')
                    print(f"   ✅ SUCCESS: Found ATM Strike {atm_strike}. CE Symbol: {ce_sym}")
                    data_found['ce_symbol'] = ce_sym
                    data_found['atm_strike'] = atm_strike
                else:
                    print(f"   ❌ FAILED: Strike {atm_strike} not found in chain.")
            else:
                print(f"   ❌ FAILED: Option Chain structure invalid. Resp keys: {chain.keys() if chain else 'None'}")
        except Exception as e:
            print(f"   ❌ ERROR in Option Chain: {e}")

    # --- 3. TEST QUOTE (THE PULSE) ---
    if 'ce_symbol' in data_found and data_found['ce_symbol'] != 'N/A':
        try:
            print("⚡ 3/3: Checking Live Quote...")
            quote = groww.get_quote(
                exchange="NSE", segment="FNO", trading_symbol=data_found['ce_symbol']
            )
            if quote:
                oi_chg = quote.get("oi_day_change_percentage", "N/A")
                ltp = quote.get("last_price", "N/A")
                print(f"   ✅ SUCCESS: CE LTP: {ltp} | OI Chg: {oi_chg}%")
                data_found['oi_chg'] = oi_chg
            else:
                print(f"   ❌ FAILED: Quote returned empty for {data_found['ce_symbol']}")
        except Exception as e:
            print(f"   ❌ ERROR in Quote: {e}")

    print("="*40)
    if len(data_found) == 4: # fut_ltp, ce_symbol, atm_strike, oi_chg
        print("🚀 ALL SYSTEMS NOMINAL. READY TO TRADE.")
    else:
        print("⚠️ SYSTEM INCOMPLETE. Fix the red errors above.")
    print("="*40 + "\n")

    return data_found

# --- RUN DIAGNOSTIC ---
groww_inst = initialize()
while True:
    diagnostic_run(groww_inst)
    print("Waiting 10 seconds for next check...")
    time.sleep(10)