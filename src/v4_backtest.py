import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys

# --- V4 CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
CAPITAL = 10000
LOT_SIZE = 75
MAX_PREMIUM = CAPITAL / LOT_SIZE 
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" # We still need a continuous feed for Trend

class NiftyV4:
    def __init__(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            self.balance = CAPITAL
            self.mov_file = "V4_BOT_MOVEMENT.csv"
            self.trade_file = "V4_TRADEBOOK.csv"
            self.expiries = [] 
            self.init_logs()
            self.load_expiries()
            print(">>> V4 Initialized. Dynamic Expiry Engine ON.")
        except Exception as e:
            print(f"Login Failed: {e}")
            sys.exit()

    def init_logs(self):
        mov_cols = ["Timestamp", "Nifty_LTP", "Expiry_Used", "Strike", "Premium", "OI_Chg", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(self.mov_file, index=False)
        trd_cols = ["Time_Entry", "Time_Exit", "Strike", "Entry_Px", "Exit_Px", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(self.trade_file, index=False)

    def load_expiries(self):
        """Fetches all valid Nifty Expiries for Dec 2025 from API"""
        print("Fetching valid expiries from NSE...")
        try:
            # We assume backtest is in Dec 2025
            resp = self.groww.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=2025, month=12)
            if 'expiries' in resp:
                self.expiries = sorted(resp['expiries']) # Sort by date
                print(f"Loaded Expiries: {self.expiries}")
            else:
                print("Error: No expiries found.")
        except Exception as e:
            print(f"Expiry Fetch Error: {e}")

    def get_dynamic_expiry(self, current_date_str):
        """Finds the nearest expiry for the current backtest date"""
        curr_dt = datetime.strptime(str(current_date_str).split('T')[0], "%Y-%m-%d")
        
        for exp in self.expiries:
            exp_dt = datetime.strptime(exp, "%Y-%m-%d")
            # If expiry is today or in future, use it
            if exp_dt >= curr_dt:
                # Groww Format: YYYY-MM-DD -> DDMonYY (e.g. 2025-12-30 -> 30Dec25)
                return exp_dt.strftime("%d%b%y") 
        return None

    def get_budget_candidates(self, nifty_px, expiry):
        """Generates symbols for ATM, OTM1, OTM2..."""
        atm = round(nifty_px / 50) * 50
        strikes = [atm, atm+50, atm+100, atm+150]
        return [f"NSE-NIFTY-{expiry}-{s}-CE" for s in strikes]

    def fetch_option_data(self, symbol, start_time, end_time):
        try:
            raw = self.groww.get_historical_candles(
                exchange="NSE", segment="FNO", groww_symbol=symbol,
                start_time=start_time, end_time=end_time, candle_interval="1minute"
            )
            if raw and 'candles' in raw and len(raw['candles']) > 0:
                return pd.DataFrame(raw['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        except:
            return None
        return None

    def run_backtest(self):
        print(f"1. Fetching Trend Data: {FUTURES_SYMBOL}...")
        data = self.groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time="2025-12-15 09:15:00", end_time="2025-12-19 15:30:00", candle_interval="5minute"
        )
        
        if not data or 'candles' not in data: return
        df = pd.DataFrame(data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        df['close'] = df['close'].ffill(); df['oi'] = df['oi'].ffill().fillna(0); df.dropna(inplace=True)
        
        # Indicators
        df['EMA5'] = df['close'].ewm(span=5).mean()
        df['EMA13'] = df['close'].ewm(span=13).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        in_pos = False
        print("2. Starting Dynamic Loop...")
        
        for i in range(13, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            clean_time = str(row['time']).replace('T', ' ')
            
            # --- DYNAMIC EXPIRY SELECTION ---
            active_expiry = self.get_dynamic_expiry(row['time'])
            if not active_expiry:
                self.log_mov(clean_time, row, "UNKNOWN", "N/A", 0, oi_chg, "SKIP", "Expiry Not Found")
                continue
            
            # Logic
            oi_chg = row['oi'] - prev_row['oi']
            trend_up = row['close'] > row['VWAP'] and row['close'] > row['EMA13']
            trigger = row['close'] > row['EMA5']
            short_covering = oi_chg < 0
            
            print(f"Time: {clean_time} | Expiry: {active_expiry} | LTP: {row['close']}", end='\r')

            if not in_pos and trend_up and trigger and short_covering:
                print(f"\n[!] Setup at {clean_time}. Hunting Budget Strike in {active_expiry}...")
                
                # Get Candidates for THIS specific expiry
                candidates = self.get_budget_candidates(row['close'], active_expiry)
                
                found = False
                for sym in candidates:
                    # Look ahead 60 mins for trade data
                    t_start = row['time']
                    try:
                        dt = datetime.strptime(str(row['time']).split('+')[0], "%Y-%m-%dT%H:%M:%S")
                    except:
                        dt = datetime.strptime(str(row['time']).split('+')[0], "%Y-%m-%d %H:%M:%S")
                    t_end = (dt + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%S")
                    
                    opt_df = self.fetch_option_data(sym, t_start, t_end)
                    
                    if opt_df is not None:
                        prem = opt_df.iloc[0]['open']
                        if prem < MAX_PREMIUM:
                            print(f"   -> FOUND: {sym} @ {prem}")
                            self.manage_trade(row, opt_df, sym, prem)
                            in_pos = True
                            found = True
                            break
                        else:
                            print(f"   -> Too Exp: {sym} @ {prem}")
                
                if not found:
                    self.log_mov(clean_time, row, active_expiry, "ALL", 0, oi_chg, "SKIP", "Over Budget")
            
            elif not in_pos:
                self.log_mov(clean_time, row, active_expiry, "N/A", 0, oi_chg, "SCAN", "Waiting")

        print("\nBacktest Complete.")

    def manage_trade(self, entry_row, opt_df, strike, entry_price):
        max_p = entry_price
        sl = entry_price - 8
        trail_active = False
        
        for j in range(len(opt_df)):
            curr = opt_df.iloc[j]['close']
            max_p = max(max_p, curr)
            if (curr - entry_price) > 10: 
                trail_active = True
                sl = max(sl, max_p - 5)
            
            reason = ""
            if curr <= sl: reason = "SL Hit"
            elif j == len(opt_df)-1: reason = "Time Exit"
            
            if reason:
                pnl = (curr - entry_price) * LOT_SIZE
                self.balance += pnl
                self.log_trade(entry_row['time'], opt_df.iloc[j]['time'], strike, entry_price, curr, pnl, self.balance, reason)
                print(f"   -> CLOSED: {reason} | PnL: {pnl:.2f}")
                return

    def log_mov(self, time, r, exp, strike, prem, oi_chg, status, reason):
        data = [time, r['close'], exp, strike, prem, oi_chg, status, reason]
        pd.DataFrame([data]).to_csv(self.mov_file, mode='a', header=False, index=False)

    def log_trade(self, et, xt, sym, ep, xp, pnl, bal, res):
        pd.DataFrame([[et, xt, sym, ep, xp, pnl, bal, res]]).to_csv(self.trade_file, mode='a', header=False, index=False)

# RUN V4
bot = NiftyV4()
bot.run_backtest()