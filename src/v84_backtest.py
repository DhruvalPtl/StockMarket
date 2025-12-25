# @title V88 - The Professional Backtester (EOD Exit + Gap Protection)
import pandas as pd
import datetime
import time
import pytz
import sys
from collections import deque, defaultdict
from growwapi import GrowwAPI

# ==========================================
# ⚙️ USER CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# Verified Symbols & Expiry
FUT_SYMBOL     = "NSE-NIFTY-30Dec25-FUT" 
OPT_EXPIRY_STR = "23Dec25"  
DAYS_TO_TEST   = 5          

# Strategy Params
VOL_MULT   = 1.5
OI_DROP    = -1.0 
START_BAL  = 10000.0
LOT_SIZE   = 75
SL_POINTS  = 4.0
TRAIL_TRIG = 3.0
TRAIL_GAP  = 2.0
# ==========================================

class BacktesterV88:
    def __init__(self):
        print(f"🔌 Connecting to Groww API...")
        try:
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            print("✅ Connection Verified.")
        except Exception as e:
            print(f"❌ Auth Error: {e}")
            sys.exit()
        
        self.option_cache = {}
        self.oi_memory = defaultdict(lambda: deque(maxlen=300))

    def get_data(self, symbol):
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=DAYS_TO_TEST)
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", symbol,
                start.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"), "1minute"
            )
            if not resp or 'candles' not in resp: return None
            df = pd.DataFrame(resp['candles'], columns=['timestamp','open','high','low','close','volume','oi'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.dropna(subset=['close'], inplace=True)
            return df.set_index('timestamp')
        except: return None

    def prepare(self):
        print(f"📥 Loading Futures: {FUT_SYMBOL}")
        self.fut_df = self.get_data(FUT_SYMBOL)
        if self.fut_df is None: return False

        # Pre-calc Indicators
        self.fut_df['vwap'] = (self.fut_df['close'] * self.fut_df['volume']).cumsum() / self.fut_df['volume'].cumsum()
        self.fut_df['avg_vol'] = self.fut_df['volume'].rolling(20).mean()

        # Identify and Load Strike Data
        min_s = int(round(self.fut_df['low'].min() / 50) * 50) - 100
        max_s = int(round(self.fut_df['high'].max() / 50) * 50) + 100
        strikes = range(min_s, max_s + 50, 50)

        print(f"📥 Loading {len(strikes)*2} Option Contracts...")
        for s in strikes:
            for t in ["CE", "PE"]:
                sym = f"NSE-NIFTY-{OPT_EXPIRY_STR}-{s}-{t}"
                df = self.get_data(sym)
                if df is not None:
                    df['panic'] = df['oi'].pct_change(3, fill_method=None) * 100
                    self.option_cache[sym] = df
        return True

    def run(self):
        if not self.prepare(): return
        
        bal = START_BAL
        trades = []
        pos = None
        active_sym, entry_p, high_p, sl_p = None, 0, 0, 0

        print(f"🚀 Simulating {len(self.fut_df)} Candles...")

        for ts, fut in self.fut_df.iterrows():
            
            # --- 1. OVERNIGHT & EOD PROTECTION ---
            # Reset memory at market open
            if ts.time() == datetime.time(9, 15):
                self.oi_memory.clear()

            # Force Exit at 3:15 PM
            if ts.time() >= datetime.time(15, 15):
                if pos:
                    opt = self.option_cache[active_sym].loc[ts]
                    pnl = (opt['close'] - entry_p) * LOT_SIZE if pos == "CE" else (entry_p - opt['close']) * LOT_SIZE
                    trades.append({'Time': ts, 'Type': 'EXIT', 'Sym': active_sym, 'Price': opt['close'], 'PnL': pnl, 'Reason': 'EOD_FORCE'})
                    bal += pnl; pos = None
                continue 

            # --- 2. SIGNALS ---
            trend = "BULLISH" if fut['close'] > fut['vwap'] else "BEARISH"
            vol_ratio = fut['volume'] / fut['avg_vol'] if fut['avg_vol'] > 0 else 0
            atm = int(round(fut['close'] / 50) * 50)

            # --- 3. ENTRY LOGIC ---
            if pos is None:
                if vol_ratio > VOL_MULT:
                    target = "CE" if trend == "BULLISH" else "PE"
                    sym = f"NSE-NIFTY-{OPT_EXPIRY_STR}-{atm}-{target}"
                    
                    if sym in self.option_cache and ts in self.option_cache[sym].index:
                        opt = self.option_cache[sym].loc[ts]
                        if opt['panic'] < OI_DROP:
                            pos, active_sym, entry_p = target, sym, opt['close']
                            sl_p, high_p = entry_p - SL_POINTS, entry_p
                            trades.append({'Time': ts, 'Type': 'ENTRY', 'Sym': sym, 'Price': entry_p, 'PnL': 0, 'Reason': 'Panic'})

            # --- 4. EXIT LOGIC ---
            elif pos:
                if active_sym in self.option_cache and ts in self.option_cache[active_sym].index:
                    opt = self.option_cache[active_sym].loc[ts]
                    
                    if opt['close'] > high_p:
                        high_p = opt['close']
                        if (high_p - entry_p) > TRAIL_TRIG:
                            sl_p = max(sl_p, high_p - TRAIL_GAP)
                    
                    if opt['low'] <= sl_p:
                        pnl = (sl_p - entry_p) * LOT_SIZE
                        bal += pnl
                        trades.append({'Time': ts, 'Type': 'EXIT', 'Sym': active_sym, 'Price': sl_p, 'PnL': pnl, 'Reason': 'StopLoss'})
                        pos = None

        # --- 5. REPORTING ---
        df_res = pd.DataFrame(trades)
        print("\n" + "="*30)
        print(f"📊 V88 BACKTEST REPORT")
        print(f"Final Balance: {bal:.2f}")
        print(f"Total PnL:     {bal - START_BAL:.2f}")
        exits = df_res[df_res['Type'] == 'EXIT']
        print(f"Total Trades:  {len(exits)}")
        if not exits.empty:
            print(f"Win Rate:      {(len(exits[exits['PnL']>0])/len(exits))*100:.1f}%")
        print("="*30)
        df_res.to_csv("V88_Final_Results.csv")

if __name__ == "__main__":
    BacktesterV88().run()