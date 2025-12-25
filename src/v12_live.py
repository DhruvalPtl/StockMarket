import time
import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys
import os

# ==========================================
# 🔴 V13 DEBUG CONFIGURATION
# ==========================================
PAPER_MODE     = True     
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# MARKET
SPOT_SYMBOL    = "NSE-NIFTY" # Try "NIFTY" if this fails
EXPIRY_DATE    = "24Dec25" 

# STRATEGY
CAPITAL        = 10000.0
QUANTITY       = 75
SL_POINTS      = 10.0
TRAIL_TRIGGER  = 10.0
TRAIL_LOCK     = 5.0
RSI_PERIOD     = 14 
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70

# FILES
LOG_MOV_FILE   = "V13_MOVEMENT.csv"
LOG_TRD_FILE   = "V13_TRADES.csv"

class LiveBotV13:
    def __init__(self):
        print("\n" + "="*40)
        print("🚀 V13 DEBUG BOT STARTED")
        print("="*40)
        
        # 1. TEST FILE WRITE
        try:
            with open("TEST_WRITE.txt", "w") as f: f.write("Write Access OK")
            print("✅ File System: OK (Can write files)")
            os.remove("TEST_WRITE.txt")
        except Exception as e:
            print(f"❌ File System Error: {e}")
            sys.exit()

        self.connect()
        self.init_logs()
        self.in_trade = False
        self.trade = {}

    def connect(self):
        print("🔌 Connecting to Groww...")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ API: Connected Successfully")
        except Exception as e:
            print(f"❌ API Connection Failed: {e}")
            print("👉 Check your API_KEY and API_SECRET.")
            sys.exit()

    def init_logs(self):
        # Create headers if missing
        if not os.path.exists(LOG_MOV_FILE):
            with open(LOG_MOV_FILE, 'w') as f:
                f.write("Timestamp,Spot,RSI,Status,Action\n")
        print(f"✅ Logs: Initialized ({LOG_MOV_FILE})")

    def log_status(self, timestamp, spot, rsi, status, action):
        try:
            with open(LOG_MOV_FILE, 'a') as f:
                f.write(f"{timestamp},{spot},{rsi},{status},{action}\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"⚠️ Log Write Failed: {e}")

    def get_market_data(self):
        """Fetches data with LOUD debugging"""
        print("📥 Fetching Market Data...", end=" ")
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            
            # DEBUG: Print exact request params
            # print(f"[Debug] Req: {SPOT_SYMBOL} from {start} to {end}")
            
            resp = self.groww.get_historical_candles(
                "NSE", "CASH", SPOT_SYMBOL, 
                start.strftime("%Y-%m-%d %H:%M:%S"), 
                end.strftime("%Y-%m-%d %H:%M:%S"), 
                "5minute"
            )
            
            # DEBUG: Print Raw Response Length
            if not resp:
                print("❌ FAILED (Response is None/Empty)")
                return None, 0
            
            candles = resp.get('candles', [])
            if not candles:
                print(f"⚠️ EMPTY (API returned 0 candles)")
                print(f"   👉 RAW RESP: {resp}")
                return None, 0
            
            print(f"✅ OK ({len(candles)} candles received)")
            
            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            current_price = df.iloc[-1]['close']
            
            # RSI Calc
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1], current_price

        except Exception as e:
            print(f"\n❌ DATA CRASH: {e}")
            return None, 0

    def get_ltp(self, symbol):
        try:
            return self.groww.get_quote("NSE", "FNO", symbol)['ltp']
        except Exception as e:
            print(f"⚠️ Quote Error ({symbol}): {e}")
            return 0

    def run(self):
        print("⏳ Loop Starting (Press Ctrl+C to Stop)")
        
        while True:
            time.sleep(2) # Fast poll
            now = datetime.now().strftime("%H:%M:%S")
            
            # 1. Fetch
            rsi, spot = self.get_market_data()
            
            if rsi is None or pd.isna(rsi):
                print(f"[{now}] No Data - Retrying...")
                continue
                
            # 2. Logic
            atm = round(spot / 50) * 50
            status = "SCAN"
            action = "Wait"
            
            print(f"[{now}] Nifty: {spot} | RSI: {int(rsi)} | ATM: {atm}", end="\r")

            if not self.in_trade:
                buy_call = rsi < RSI_OVERSOLD
                buy_put  = rsi > RSI_OVERBOUGHT
                
                if buy_call or buy_put:
                    # Signal!
                    type_str = "CE" if buy_call else "PE"
                    sym = f"NSE-NIFTY-{EXPIRY_DATE}-{atm}-{type_str}"
                    ltp = self.get_ltp(sym)
                    
                    if ltp > 0:
                        print(f"\n🚀 SIGNAL: {type_str} on {sym} @ {ltp}")
                        # Place Paper Order
                        self.in_trade = True
                        self.trade = {'sym': sym, 'entry': ltp, 'sl': ltp - SL_POINTS, 'peak': ltp, 'sl_moved': False}
                        status = "ENTRY"
                        action = f"Bought {type_str}"
            
            else:
                # Manage
                sym = self.trade['sym']
                ltp = self.get_ltp(sym)
                status = "HOLD"
                action = f"PnL: {(ltp - self.trade['entry']) * QUANTITY:.0f}"
                
                # Exit logic (Simplified for debug)
                if ltp < self.trade['sl']:
                    print(f"\n🔴 SL HIT: {sym}")
                    self.in_trade = False
                    status = "EXIT"
                    action = "SL Hit"

            # 3. Log
            self.log_status(now, spot, int(rsi), status, action)

if __name__ == "__main__":
    LiveBotV13().run()