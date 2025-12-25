import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import time
import sys # For flush printing

# --- V3.3 CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# 1. FUTURES SYMBOL (Your Trend Source)
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 

# 2. OPTION EXPIRY (Must be correct for trades to fire)
# Dec 25 is Christmas. Try '24Dec25' (Wed) or '30Dec25' (if Monthly).
OPTION_EXPIRY = "30Dec25" 

CAPITAL = 10000
LOT_SIZE = 75
MAX_PREMIUM = CAPITAL / LOT_SIZE 
RESISTANCE_BUFFER = 10 
TRAIL_TRIGGER = 10  
TRAIL_GAP = 5       

class NiftyV3_3:
    def __init__(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            self.balance = CAPITAL
            self.mov_file = "V3_BOT_MOVEMENT.csv"
            self.trade_file = "V3_TRADEBOOK.csv"
            self.init_logs()
            print(">>> V3.3 Initialized. Logging enabled.")
        except Exception as e:
            print(f"Login Failed: {e}")
            sys.exit()

    def init_logs(self):
        mov_cols = ["Timestamp", "Nifty_LTP", "VWAP", "EMA5", "EMA13", "Looking_At_Strike", 
                    "Strike_Price", "OI", "OI_Change", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(self.mov_file, index=False)
        
        trd_cols = ["Time_Entry", "Time_Exit", "Strike_Name", "Nifty_Entry", "Nifty_Exit", 
                    "Opt_Entry", "Opt_Exit", "Max_Price", "Trailing_Px", "SL_Price", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(self.trade_file, index=False)

    def get_budget_strike(self, nifty_price):
        """Finds ATM Strike"""
        atm = round(nifty_price / 50) * 50
        # Construct symbol using the OPTION_EXPIRY variable
        symbol = f"NSE-NIFTY-{OPTION_EXPIRY}-{atm}-CE"
        return symbol
            
    def fetch_option_data(self, symbol, start_time, end_time):
        """Fetches ACTUAL history for the specific option strike"""
        try:
            raw = self.groww.get_historical_candles(
                exchange="NSE", segment="FNO", groww_symbol=symbol,
                start_time=start_time, end_time=end_time, candle_interval="1minute"
            )
            if raw and 'candles' in raw and len(raw['candles']) > 0:
                return pd.DataFrame(raw['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        except Exception as e:
            return None
        return None

    def run_backtest(self):
        print(f"1. Fetching Futures Data: {FUTURES_SYMBOL}...")
        
        data = self.groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time="2025-12-15 09:15:00", end_time="2025-12-19 15:30:00", candle_interval="5minute"
        )
        
        if not data or 'candles' not in data or len(data['candles']) == 0:
            print(f"CRITICAL ERROR: No data for {FUTURES_SYMBOL}. Check Symbol/Holiday.")
            return

        df = pd.DataFrame(data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        # Data Cleaning
        df['close'] = df['close'].ffill()
        df['high'] = df['high'].ffill() 
        df['low'] = df['low'].ffill()
        df['open'] = df['open'].ffill()
        df['oi'] = df['oi'].ffill().fillna(0)
        df.dropna(subset=['close'], inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        print(f"2. Data Stabilized: {len(df)} candles ready. Calculating Indicators...")

        # Indicators
        df['EMA5'] = df['close'].ewm(span=5).mean()
        df['EMA13'] = df['close'].ewm(span=13).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        day_high = 0
        in_pos = False
        
        print("3. Starting Loop... (Press Ctrl+C to stop)")
        print("-" * 60)

        for i in range(13, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # --- VISUAL HEARTBEAT ---
            # Prints every candle to show it's alive
            print(f"Processing {row['time']} | LTP: {row['close']} | OI Chg: {int(row['oi'] - prev_row['oi'])}", end='\r')
            
            if "09:15" in str(row['time']): day_high = 0 
            day_high = max(day_high, row['high'])
            
            oi_chg = row['oi'] - prev_row['oi']
            trend_up = row['close'] > row['VWAP'] and row['close'] > row['EMA13']
            trigger = row['close'] > row['EMA5']
            short_covering = oi_chg < 0
            
            dist_to_high = day_high - row['close']
            safe_from_resistance = (dist_to_high > RESISTANCE_BUFFER) or (dist_to_high < 0)

            current_strike = self.get_budget_strike(row['close'])
            
            if not in_pos:
                if trend_up and trigger and short_covering and safe_from_resistance:
                    # SETUP FOUND - Try to fetch option
                    print(f"\n[!] Setup Found at {row['time']}. Fetching {current_strike}...")
                    
                    try:
                        dt_obj = datetime.strptime(str(row['time']).split('+')[0], "%Y-%m-%dT%H:%M:%S")
                    except:
                        continue
                        
                    trade_end = (dt_obj + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%S")
                    
                    opt_df = self.fetch_option_data(current_strike, row['time'], trade_end)
                    
                    if opt_df is not None and not opt_df.empty:
                        entry_prem = opt_df.iloc[0]['open']
                        if entry_prem < MAX_PREMIUM:
                            print(f"   -> BUYING {current_strike} @ {entry_prem}")
                            in_pos = True
                            self.manage_trade(row, opt_df, current_strike, entry_prem)
                        else:
                            print(f"   -> SKIPPING: Price {entry_prem} > Budget {int(MAX_PREMIUM)}")
                            self.log_mov(row, current_strike, entry_prem, oi_chg, "SKIP", "Premium > Budget")
                    else:
                        print(f"   -> FAILED: Data missing for {current_strike}. Check Expiry.")
                        self.log_mov(row, current_strike, 0, oi_chg, "SKIP", "Option Data Missing")
                else:
                    reason = "Waiting"
                    if not safe_from_resistance: reason = f"Near DayHigh ({dist_to_high:.1f}pts)"
                    elif not short_covering: reason = "No Short Covering"
                    self.log_mov(row, current_strike, 0, oi_chg, "SCAN", reason)
        
        print("\n" + "-" * 60)
        print("Backtest Complete. Check V3_TRADEBOOK.csv")

    def manage_trade(self, entry_row, opt_df, strike, entry_price):
        max_price = entry_price
        sl_price = entry_price - (8)
        trail_active = False
        
        for j in range(len(opt_df)):
            candle = opt_df.iloc[j]
            curr_price = candle['close']
            max_price = max(max_price, curr_price)
            
            profit = curr_price - entry_price
            if profit >= TRAIL_TRIGGER:
                trail_active = True
                new_sl = max_price - TRAIL_GAP
                if new_sl > sl_price: sl_price = new_sl
            
            exit_reason = ""
            if curr_price <= sl_price: exit_reason = "SL Hit"
            elif j == len(opt_df)-1: exit_reason = "Time Exit (1hr)"
            
            if exit_reason:
                pnl = (curr_price - entry_price) * LOT_SIZE
                self.balance += pnl
                self.log_trade([entry_row['time'], candle['time'], strike, entry_row['close'], "-", 
                               entry_price, curr_price, max_price, 
                               "Active" if trail_active else "Pending", sl_price, pnl, self.balance, exit_reason])
                print(f"   -> CLOSED: PnL {pnl:.2f} ({exit_reason})")
                return

    def log_mov(self, r, strike, opt_px, oi_chg, status, reason):
        data = [r['time'], r['close'], round(r['VWAP'],1), round(r['EMA5'],1), round(r['EMA13'],1), 
                strike, opt_px, r['oi'], oi_chg, status, reason]
        pd.DataFrame([data]).to_csv(self.mov_file, mode='a', header=False, index=False)

    def log_trade(self, data):
        pd.DataFrame([data]).to_csv(self.trade_file, mode='a', header=False, index=False)

# RUN V3.3
bot = NiftyV3_3()
bot.run_backtest()