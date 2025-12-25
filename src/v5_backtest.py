import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys

# --- V5 CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
CAPITAL = 10000
LOT_SIZE = 75
MAX_PREMIUM = 140 # Slightly increased to catch moves
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" # For OI & VWAP
SPOT_SYMBOL = "NSE-NIFTY"              # For Price & Strike Selection

class NiftyV5:
    def __init__(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            self.balance = CAPITAL
            self.mov_file = "V5_BOT_MOVEMENT1.csv"
            self.trade_file = "V5_TRADEBOOK1.csv"
            self.expiries = [] 
            self.init_logs()
            self.load_expiries()
            print(">>> V5 Dual-Core Initialized (Spot + Futures).")
        except Exception as e:
            print(f"Login Failed: {e}")
            sys.exit()

    def init_logs(self):
        mov_cols = ["Timestamp", "Spot_LTP", "Fut_LTP", "VWAP(F)", "EMA5(S)", "OI_Chg", "RSI", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(self.mov_file, index=False)
        trd_cols = ["Time_Entry", "Time_Exit", "Strike", "Spot_Entry", "Entry_Px", "Exit_Px", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(self.trade_file, index=False)

    def load_expiries(self):
        try:
            resp = self.groww.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=2025, month=12)
            if 'expiries' in resp:
                self.expiries = sorted(resp['expiries'])
                print(f"Loaded Expiries: {self.expiries}")
        except:
            pass

    def get_dynamic_expiry(self, current_date_str):
        curr_dt = datetime.strptime(str(current_date_str).split('T')[0], "%Y-%m-%d")
        for exp in self.expiries:
            exp_dt = datetime.strptime(exp, "%Y-%m-%d")
            if exp_dt >= curr_dt:
                return exp_dt.strftime("%d%b%y") 
        return None

    def get_budget_candidates(self, spot_px, expiry):
        # STRIKE SELECTION BASED ON SPOT PRICE (Corrected)
        atm = round(spot_px / 50) * 50
        strikes = [atm, atm+50, atm+100]
        return [f"NSE-NIFTY-{expiry}-{s}-CE" for s in strikes]

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def fetch_data(self, symbol):
        data = self.groww.get_historical_candles(
            exchange="NSE", segment="FNO" if "FUT" in symbol else "CASH", 
            groww_symbol=symbol,
            start_time="2025-11-19 09:15:00", end_time="2025-12-19 15:30:00", candle_interval="5minute"
        )
        if not data or 'candles' not in data: return pd.DataFrame()
        df = pd.DataFrame(data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        df['close'] = df['close'].ffill(); 
        if 'oi' in df.columns: df['oi'] = df['oi'].ffill().fillna(0)
        return df

    def run_backtest(self):
        print("1. Fetching Futures (Institutions)...")
        fut_df = self.fetch_data(FUTURES_SYMBOL)
        
        print("2. Fetching Spot (Price Action)...")
        spot_df = self.fetch_data(SPOT_SYMBOL)

        if fut_df.empty or spot_df.empty:
            print("CRITICAL: Data missing.")
            return

        # MERGE DATA (Sync Futures & Spot by Time)
        # Suffix _F = Futures, _S = Spot
        df = pd.merge(fut_df, spot_df, on='time', suffixes=('_F', '_S'))
        
        # --- INDICATORS ---
        # VWAP on Futures (Volume is real)
        df['VWAP_F'] = (df['volume_F'] * (df['high_F'] + df['low_F'] + df['close_F']) / 3).cumsum() / df['volume_F'].cumsum()
        
        # EMA & RSI on Spot (Price is real)
        df['EMA5_S'] = df['close_S'].ewm(span=5).mean()
        df['EMA13_S'] = df['close_S'].ewm(span=13).mean()
        df['RSI_S'] = self.calculate_rsi(df['close_S'])
        
        in_pos = False
        print(f"3. Engine Started. Analyzing {len(df)} candles...")
        print("-" * 70)
        
        for i in range(14, len(df)): # Start at 14 for RSI
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            clean_time = str(row['time']).replace('T', ' ')
            
            # Data Points
            spot_ltp = row['close_S']
            fut_ltp = row['close_F']
            vwap = row['VWAP_F']
            oi_chg = row['oi_F'] - prev_row['oi_F']
            rsi = row['RSI_S']
            
            # --- V5 STRATEGY ENGINE ---
            # 1. Trend: Spot > EMA13 AND Future > VWAP (Double Confirmation)
            trend_up = spot_ltp > row['EMA13_S'] and fut_ltp > vwap
            
            # 2. Trigger: Spot Momentum
            trigger = spot_ltp > row['EMA5_S'] and rsi > 55
            
            # 3. Validation: Short Covering (Futures OI Drop)
            short_covering = oi_chg < 0
            
            # Expiry Check
            active_expiry = self.get_dynamic_expiry(row['time'])
            if not active_expiry: continue

            # ENTRY
            if not in_pos and trend_up and trigger and short_covering:
                print(f"\n[!] Signal at {clean_time} | Spot: {spot_ltp} | RSI: {int(rsi)}")
                
                # Fetch Candidates based on SPOT PRICE
                candidates = self.get_budget_candidates(spot_ltp, active_expiry)
                
                for sym in candidates:
                    # Fetch Option Data
                    try:
                         # Handle time formatting
                        t_parts = str(row['time']).split('+')[0].replace('T', ' ')
                        dt = datetime.strptime(t_parts, "%Y-%m-%d %H:%M:%S")
                        t_end = (dt + timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S") # 45 min max hold
                        
                        # API Call for Option
                        raw_opt = self.groww.get_historical_candles(
                            "NSE", "FNO", sym, str(row['time']), t_end, "1minute"
                        )
                    except: continue

                    if raw_opt and 'candles' in raw_opt:
                        opt_data = raw_opt['candles']
                        entry_prem = opt_data[0][1] # Open price of first candle
                        
                        if entry_prem < MAX_PREMIUM:
                            print(f"   -> BUY {sym} @ {entry_prem}")
                            self.manage_trade(clean_time, opt_data, sym, entry_prem, spot_ltp)
                            in_pos = False # Allow re-entry
                            break
                
                # If loop finishes without trade, log skip
                self.log_mov(clean_time, spot_ltp, fut_ltp, vwap, row['EMA5_S'], oi_chg, rsi, "SKIP", "Over Budget")

            elif not in_pos:
                reason = "Waiting"
                if not trend_up: reason = "No Trend (Spot<EMA13 or Fut<VWAP)"
                elif not trigger: reason = f"Low Momentum (RSI {int(rsi)})"
                elif not short_covering: reason = "OI Increasing"
                
                self.log_mov(clean_time, spot_ltp, fut_ltp, vwap, row['EMA5_S'], oi_chg, rsi, "SCAN", reason)

        print("\n" + "-" * 70)
        print("V5 Backtest Complete.")

    def manage_trade(self, entry_time, opt_candles, strike, entry_price, spot_ref):
        max_p = entry_price
        sl = entry_price - 8 # Hard SL
        
        for k in range(len(opt_candles)):
            candle = opt_candles[k] # [time, open, high, low, close...]
            curr = candle[4] # Close
            max_p = max(max_p, curr)
            
            # Trail SL: If profit > 10, Lock SL at Breakeven + 2
            if (curr - entry_price) > 10:
                sl = max(sl, entry_price + 2)
            # If profit > 20, Trail tight (Max - 5)
            if (curr - entry_price) > 20:
                sl = max(sl, max_p - 5)

            exit_reason = ""
            if curr <= sl: exit_reason = "SL Hit"
            elif k == len(opt_candles)-1: exit_reason = "Time Exit"

            if exit_reason:
                pnl = (curr - entry_price) * LOT_SIZE
                self.balance += pnl
                # Convert epoch timestamp if needed, or use index
                exit_time = str(candle[0]) 
                self.log_trade(entry_time, exit_time, strike, spot_ref, entry_price, curr, pnl, self.balance, exit_reason)
                print(f"   -> CLOSED: {exit_reason} | PnL: {pnl:.2f}")
                return

    def log_mov(self, time, spot, fut, vwap, ema, oi, rsi, status, reason):
        data = [time, spot, fut, round(vwap,1), round(ema,1), oi, round(rsi,1), status, reason]
        pd.DataFrame([data]).to_csv(self.mov_file, mode='a', header=False, index=False)

    def log_trade(self, et, xt, sym, sept, ep, xp, pnl, bal, res):
        pd.DataFrame([[et, xt, sym, sept, ep, xp, pnl, bal, res]]).to_csv(self.trade_file, mode='a', header=False, index=False)

# RUN V5
bot = NiftyV5()
bot.run_backtest()