import time
import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys
import os

# ==========================================
# 🔴 V15 CONFIGURATION
# ==========================================
PAPER_MODE     = True     
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# 📅 EXPIRY SETTINGS
# Use YYYY-MM-DD format (The date you tested successfully)
EXPIRY_DATE    = "2025-12-23" 

# FUT_SYMBOL (For VWAP - Ensure this matches the Active Monthly Future)
FUT_SYMBOL     = "NSE-NIFTY-30Dec25-FUT" 

# STRATEGY
CAPITAL        = 10000.0
QUANTITY       = 75
SL_POINTS      = 5.0
TRAIL_TRIGGER  = 4.0
TRAIL_LOCK     = 3.0
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70

# FILES
LOG_MOV_FILE   = f"Bot_Movment_{datetime.now().strftime('%Y%m%d')}.csv"
LOG_TRD_FILE   = f"Trade_Book_{datetime.now().strftime('%Y%m%d')}.csv"

class LiveBotV15:
    def __init__(self):
        print(f"\n🚀 V15 STRUCTURAL FIX | MODE: {'PAPER' if PAPER_MODE else 'REAL MONEY'}")
        
        # Date Logic
        try:
            self.expiry_dt = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")
            self.symbol_date_str = self.expiry_dt.strftime("%d%b%y").upper() # 23DEC25
            print(f"📅 API Expiry: {EXPIRY_DATE}")
            print(f"🔠 Symbol Tag: {self.symbol_date_str}")
        except ValueError:
            print(f"❌ ERROR: EXPIRY_DATE '{EXPIRY_DATE}' must be YYYY-MM-DD"); sys.exit()

        print(f"📍 LOGS: {os.getcwd()}")
        self.connect()
        self.init_logs()
        self.in_trade = False
        self.trade = {}
        self.prev_oi = {'CE': 0, 'PE': 0}

    def connect(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ API Connected.")
        except Exception as e:
            print(f"❌ Connection Failed: {e}"); sys.exit()

    def init_logs(self):
        if not os.path.exists(LOG_MOV_FILE):
            cols = [
                "Timestamp", "Nifty_Price", "VWAP", "EMA5", "EMA13", 
                "Strike_Looking", "CE_Price", "PE_Price", "CE_OI", "PE_OI", "OI_Change_CE", "OI_Change_PE",
                "PCR", "CE_Delta", "CE_Theta", "CE_Gamma", "CE_Vega", "PE_Delta", "PE_Theta", 
                "Status_of_Trade", "Reason"
            ]
            with open(LOG_MOV_FILE, 'w') as f: f.write(",".join(cols) + "\n")

        if not os.path.exists(LOG_TRD_FILE):
            cols = [
                "Time_Buy", "Time_Sell", "Strike_Name", "Type", 
                "Nifty_Entry", "Nifty_Exit", "Opt_Entry", "Opt_Exit", 
                "Max_Price", "Trailing_SL_Price", "Stop_Loss_Price", 
                "PnL", "Balance", "Reason"
            ]
            with open(LOG_TRD_FILE, 'w') as f: f.write(",".join(cols) + "\n")

    def log_movement(self, row_data):
        try:
            with open(LOG_MOV_FILE, 'a') as f:
                f.write(",".join(map(str, row_data)) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except: pass

    def log_trade(self, t, exit_time, nifty_exit, opt_exit, reason):
        pnl = (opt_exit - t['entry_p']) * QUANTITY
        row = [
            t['entry_time'], exit_time, t['symbol'], t['type'],
            t['nifty_entry'], nifty_exit, t['entry_p'], opt_exit,
            t['peak'], t['sl'], t['orig_sl'], 
            round(pnl, 2), CAPITAL + pnl, reason
        ]
        try:
            with open(LOG_TRD_FILE, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except: pass

    def get_indicators(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            
            spot_resp = self.groww.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "5minute")
            if not spot_resp: return None
            df = pd.DataFrame(spot_resp['candles'], columns=['time', 'o', 'h', 'l', 'c', 'v', 'oi'])
            
            ema5 = df['c'].ewm(span=5, adjust=False).mean().iloc[-1]
            ema13 = df['c'].ewm(span=13, adjust=False).mean().iloc[-1]
            spot_price = df['c'].iloc[-1]
            
            delta = df['c'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            fut_resp = self.groww.get_historical_candles("NSE", "FNO", FUT_SYMBOL, start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "5minute")
            if fut_resp:
                df_fut = pd.DataFrame(fut_resp['candles'], columns=['time', 'o', 'h', 'l', 'c', 'v', 'oi'])
                vwap = (df_fut['c'] * df_fut['v']).cumsum() / df_fut['v'].cumsum()
                vwap_val = vwap.iloc[-1]
            else:
                vwap_val = 0
            
            return spot_price, rsi.iloc[-1], ema5, ema13, vwap_val
        except: return None

    # ------------------------------------------------------------------
    # 🛠️ FIXED: PARSING THE DICTIONARY STRUCTURE (User Provided Logic)
    # ------------------------------------------------------------------
    def get_chain_data(self, atm_strike):
        try:
            chain = self.groww.get_option_chain("NSE", "NIFTY", EXPIRY_DATE)
            
            # Check if valid structure exists
            if not chain or 'strikes' not in chain:
                # Debug print only if failing
                # print(f"⚠️ Chain Raw keys: {chain.keys() if chain else 'None'}") 
                return None
            
            total_ce_oi = 0
            total_pe_oi = 0
            
            # Defaults
            ce_data = {'price': 0, 'oi': 0, 'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0}
            pe_data = {'price': 0, 'oi': 0, 'delta': 0, 'theta': 0}
            found_atm = False
            
            # Iterate through the Dictionary items
            for strike_str, strike_data in chain['strikes'].items():
                strike_price = float(strike_str)
                
                # 1. Extract Call Data
                ce_node = strike_data.get('CE')
                if ce_node:
                    ce_oi = ce_node.get('open_interest', 0)
                    total_ce_oi += ce_oi
                    
                    # Capture ATM Call
                    if strike_price == atm_strike:
                        greeks = ce_node.get('greeks', {})
                        ce_data = {
                            'price': ce_node.get('ltp', 0),
                            'oi': ce_oi,
                            'delta': greeks.get('delta', 0),
                            'theta': greeks.get('theta', 0),
                            'gamma': greeks.get('gamma', 0),
                            'vega': greeks.get('vega', 0)
                        }

                # 2. Extract Put Data
                pe_node = strike_data.get('PE')
                if pe_node:
                    pe_oi = pe_node.get('open_interest', 0)
                    total_pe_oi += pe_oi
                    
                    # Capture ATM Put
                    if strike_price == atm_strike:
                        greeks = pe_node.get('greeks', {})
                        pe_data = {
                            'price': pe_node.get('ltp', 0),
                            'oi': pe_oi,
                            'delta': greeks.get('delta', 0),
                            'theta': greeks.get('theta', 0)
                        }
                        found_atm = True

            pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
            
            if not found_atm:
                # print(f"⚠️ ATM Strike {atm_strike} not found in chain.")
                return None
                
            return ce_data, pe_data, pcr

        except Exception as e:
            print(f"❌ Chain Parse Error: {e}")
            return None

    def run(self):
        print("⏳ Waiting for Market Data...")
        
        while True:
            time.sleep(1)
            now_str = datetime.now().strftime("%H:%M:%S")
            
            # 1. Fetch Indicators
            res = self.get_indicators()
            if not res: 
                print(f"[{now_str}] Fetching Indicators...", end='\r')
                continue
            spot, rsi, ema5, ema13, vwap = res
            
            atm = round(spot / 50) * 50
            
            # 2. Fetch Chain (Using NEW Logic)
            chain_res = self.get_chain_data(atm)
            if not chain_res: 
                print(f"[{now_str}] Fetching Chain for {atm}...", end='\r')
                continue
            ce, pe, pcr = chain_res
            
            # OI Change
            ce_oi_chg = ce['oi'] - self.prev_oi['CE']
            pe_oi_chg = pe['oi'] - self.prev_oi['PE']
            self.prev_oi = {'CE': ce['oi'], 'PE': pe['oi']}
            
            # 3. LOGIC
            status = "SCAN"
            reason = "Waiting"
            
            if not self.in_trade:
                buy_call = rsi < RSI_OVERSOLD
                buy_put  = rsi > RSI_OVERBOUGHT
                
                if buy_call or buy_put:
                    target_type = "CE" if buy_call else "PE"
                    target_px = ce['price'] if buy_call else pe['price']
                    
                    # Construct Standard Symbol for Order Placement
                    # Format: NSE-NIFTY-23Dec25-24000-CE
                    sym = f"NSE-NIFTY-{self.symbol_date_str}-{atm}-{target_type}"
                    
                    if target_px > 0 and (target_px * QUANTITY <= CAPITAL):
                        print(f"\n🚀 SIGNAL: {target_type} @ {target_px} (RSI {int(rsi)})")
                        self.in_trade = True
                        self.trade = {
                            'symbol': sym, 'type': target_type, 'entry_p': target_px,
                            'sl': target_px - SL_POINTS, 'orig_sl': target_px - SL_POINTS,
                            'peak': target_px, 'entry_time': now_str, 
                            'nifty_entry': spot, 'sl_moved': False
                        }
                        status = "ENTRY"
                        reason = f"RSI {int(rsi)} Reversal"
            else:
                curr_px = ce['price'] if self.trade['type'] == 'CE' else pe['price']
                status = "HOLD"
                
                # Update Peak & Trail
                if curr_px > self.trade['peak']: self.trade['peak'] = curr_px
                profit = curr_px - self.trade['entry_p']
                
                if profit >= TRAIL_TRIGGER and not self.trade['sl_moved']:
                    self.trade['sl'] = self.trade['entry_p'] + TRAIL_LOCK
                    self.trade['sl_moved'] = True
                    print(f"🔒 SL Locked at {self.trade['sl']}")
                
                # Exit
                exit_msg = None
                if curr_px <= self.trade['sl']: exit_msg = "SL Hit"
                elif datetime.now().hour == 15 and datetime.now().minute >= 20: exit_msg = "EOD Force"
                
                if exit_msg:
                    print(f"🔴 EXIT: {self.trade['symbol']} @ {curr_px} ({exit_msg})")
                    self.log_trade(self.trade, now_str, spot, curr_px, exit_msg)
                    self.in_trade = False
                    status = "EXIT"

            # 4. LOG & PRINT
            row = [
                now_str, spot, round(vwap, 2), round(ema5, 2), round(ema13, 2),
                atm, ce['price'], pe['price'], ce['oi'], pe['oi'], ce_oi_chg, pe_oi_chg,
                pcr, ce['delta'], ce['theta'], ce['gamma'], ce['vega'], pe['delta'], pe['theta'],
                status, reason
            ]
            self.log_movement(row)
            print(f"[{now_str}] Spot:{spot} | RSI:{int(rsi)} | PCR:{pcr} | CE:{ce['price']} PE:{pe['price']} | {status}   ", end='\r')

if __name__ == "__main__":
    LiveBotV15().run()