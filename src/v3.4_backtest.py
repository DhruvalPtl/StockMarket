import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys

# --- V3.4 CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 
OPTION_EXPIRY = "30Dec25"  # Hardcoded as requested

CAPITAL = 10000
LOT_SIZE = 75
MAX_PREMIUM = CAPITAL / LOT_SIZE  # approx 133
RESISTANCE_BUFFER = 10 
TRAIL_TRIGGER = 10  
TRAIL_GAP = 5       

class NiftyV3_4:
    def __init__(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            self.balance = CAPITAL
            self.mov_file = "V3.4_BOT_MOVEMENT.csv"
            self.trade_file = "V3.4_TRADEBOOK.csv"
            self.init_logs()
            print(">>> V3.4 Initialized. Timestamp Fixed. Budget Hunting ON.")
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

    def format_time(self, t_str):
        """Removes 'T' from timestamp"""
        return str(t_str).replace('T', ' ')

    def get_strike_candidates(self, nifty_price):
        """Returns [ATM, ATM+50, ATM+100] to find one that fits budget"""
        atm = round(nifty_price / 50) * 50
        # Priority: ATM -> OTM 1 -> OTM 2 -> OTM 3
        strikes = [atm, atm+50, atm+100, atm+150]
        symbols = [f"NSE-NIFTY-{OPTION_EXPIRY}-{s}-CE" for s in strikes]
        return symbols
            
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
        print(f"1. Fetching Futures Data: {FUTURES_SYMBOL}...")
        
        data = self.groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time="2025-12-15 09:15:00", end_time="2025-12-19 15:30:00", candle_interval="5minute"
        )
        
        if not data or 'candles' not in data or len(data['candles']) == 0:
            print(f"CRITICAL ERROR: No data for {FUTURES_SYMBOL}.")
            return

        df = pd.DataFrame(data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        # Clean Data
        df['close'] = df['close'].ffill()
        df['high'] = df['high'].ffill() 
        df['low'] = df['low'].ffill()
        df['open'] = df['open'].ffill()
        df['oi'] = df['oi'].ffill().fillna(0)
        df.dropna(subset=['close'], inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        print(f"2. Data Stabilized: {len(df)} candles.")

        # Indicators
        df['EMA5'] = df['close'].ewm(span=5).mean()
        df['EMA13'] = df['close'].ewm(span=13).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        day_high = 0
        in_pos = False
        
        print("3. Starting Loop... (Ctrl+C to stop)")
        print("-" * 65)

        for i in range(13, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            clean_time = self.format_time(row['time'])
            
            # Heartbeat
            print(f"Processing {clean_time} | LTP: {row['close']} | OI Chg: {int(row['oi'] - prev_row['oi'])}", end='\r')
            
            if "09:15" in str(row['time']): day_high = 0 
            day_high = max(day_high, row['high'])
            
            oi_chg = row['oi'] - prev_row['oi']
            trend_up = row['close'] > row['VWAP'] and row['close'] > row['EMA13']
            trigger = row['close'] > row['EMA5']
            short_covering = oi_chg < 0
            
            dist_to_high = day_high - row['close']
            safe_from_resistance = (dist_to_high > RESISTANCE_BUFFER) or (dist_to_high < 0)

            # Get List of Candidates (ATM, OTM1, OTM2)
            strike_candidates = self.get_strike_candidates(row['close'])
            
            if not in_pos:
                if trend_up and trigger and short_covering and safe_from_resistance:
                    print(f"\n[!] Setup at {clean_time}. Hunting for Budget Strike (< {int(MAX_PREMIUM)})...")
                    
                    found_trade = False
                    for strike in strike_candidates:
                        try:
                            # Parse time safely
                            dt_obj = datetime.strptime(str(row['time']).split('+')[0].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
                        except:
                            dt_obj = datetime.strptime(str(row['time']).split('+')[0], "%Y-%m-%dT%H:%M:%S")

                        trade_end = (dt_obj + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%S")
                        
                        opt_df = self.fetch_option_data(strike, row['time'], trade_end)
                        
                        if opt_df is not None and not opt_df.empty:
                            entry_prem = opt_df.iloc[0]['open']
                            if entry_prem < MAX_PREMIUM:
                                print(f"   -> FOUND {strike} @ {entry_prem} (Budget OK)")
                                in_pos = True
                                found_trade = True
                                self.manage_trade(row, opt_df, strike, entry_prem)
                                break # Stop looking, we found one
                            else:
                                print(f"   -> Skip {strike} @ {entry_prem} (Too Exp)")
                        else:
                             print(f"   -> No Data for {strike}")

                    if not found_trade:
                         self.log_mov(clean_time, row, "ALL_EXPENSIVE", 0, oi_chg, "SKIP", "All Strikes > Budget")

                else:
                    reason = "Waiting"
                    if not safe_from_resistance: reason = f"Near DayHigh ({dist_to_high:.1f}pts)"
                    elif not short_covering: reason = "No Short Covering"
                    self.log_mov(clean_time, row, strike_candidates[0], 0, oi_chg, "SCAN", reason)
        
        print("\n" + "-" * 65)
        print("Backtest Complete.")

    def manage_trade(self, entry_row, opt_df, strike, entry_price):
        max_price = entry_price
        sl_price = entry_price - (8)
        trail_active = False
        clean_entry_time = self.format_time(entry_row['time'])
        
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
                clean_exit_time = self.format_time(candle['time'])
                
                self.log_trade([clean_entry_time, clean_exit_time, strike, entry_row['close'], "-", 
                               entry_price, curr_price, max_price, 
                               "Active" if trail_active else "Pending", sl_price, pnl, self.balance, exit_reason])
                print(f"   -> CLOSED: PnL {pnl:.2f} ({exit_reason})")
                return

    def log_mov(self, clean_time, r, strike, opt_px, oi_chg, status, reason):
        data = [clean_time, r['close'], round(r['VWAP'],1), round(r['EMA5'],1), round(r['EMA13'],1), 
                strike, opt_px, r['oi'], oi_chg, status, reason]
        pd.DataFrame([data]).to_csv(self.mov_file, mode='a', header=False, index=False)

    def log_trade(self, data):
        pd.DataFrame([data]).to_csv(self.trade_file, mode='a', header=False, index=False)

# RUN V3.4
bot = NiftyV3_4()
bot.run_backtest()