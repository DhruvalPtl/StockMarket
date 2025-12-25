# @title V91 - The Final Backtester (Trade Book + Morning Filter)
import pandas as pd
import datetime
import time
import sys
from growwapi import GrowwAPI

# ==========================================
# ⚙️ SETTINGS
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

FUT_SYMBOL     = "NSE-NIFTY-30Dec25-FUT" 
OPT_EXPIRY_STR = "23Dec25"  
DAYS_TO_TEST   = 5          

# Strategy Params
VOL_MULT   = 1.5
OI_DROP    = -1.0 
START_BAL  = 10000.0
LOT_SIZE   = 75
SL_POINTS  = 4.0   
TRAIL_TRIG = 4.0   # Wait for 4 points to start trailing
TRAIL_GAP  = 2.0   
# ==========================================

class BacktesterV91:
    def __init__(self):
        try:
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            self.option_cache = {}
            print("✅ Connection Verified.")
        except Exception as e:
            print(f"❌ Auth Error: {e}"); sys.exit()

    def get_data(self, symbol):
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=DAYS_TO_TEST)
        try:
            resp = self.groww.get_historical_candles("NSE", "FNO", symbol,
                start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "1minute")
            df = pd.DataFrame(resp['candles'], columns=['timestamp','open','high','low','close','volume','oi'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df.set_index('timestamp')
        except: return None

    def prepare(self):
        print(f"📥 Loading Data for {FUT_SYMBOL}...")
        self.fut_df = self.get_data(FUT_SYMBOL)
        if self.fut_df is None: return False
        self.fut_df['vwap'] = (self.fut_df['close'] * self.fut_df['volume']).cumsum() / self.fut_df['volume'].cumsum()
        self.fut_df['avg_vol'] = self.fut_df['volume'].rolling(20).mean()
        
        strikes = range(int(round(self.fut_df['low'].min()/50)*50)-50, int(round(self.fut_df['high'].max()/50)*50)+100, 50)
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
        bal, trades, pos = START_BAL, [], None
        active_sym, entry_p, high_p, sl_p, entry_t = None, 0, 0, 0, None

        for ts, fut in self.fut_df.iterrows():
            curr_time = ts.time()
            # 1. EOD Exit (Force exit at 3:15 PM)
            if curr_time >= datetime.time(15, 15):
                if pos:
                    opt = self.option_cache[active_sym].loc[ts]
                    pnl = (opt['close'] - entry_p) * LOT_SIZE
                    trades.append({'Entry': entry_t, 'Exit': ts, 'Sym': active_sym, 'Buy': entry_p, 'Sell': opt['close'], 'PnL': pnl, 'Reason': 'EOD'})
                    bal += pnl; pos = None
                continue 

            # 2. Signals
            trend = "BULLISH" if fut['close'] > fut['vwap'] else "BEARISH"
            vol_ratio = fut['volume'] / fut['avg_vol'] if fut['avg_vol'] > 0 else 0
            
            # 3. Entry (Morning Only: 09:15 - 11:30)
            if pos is None and (datetime.time(9,15) <= curr_time <= datetime.time(11,30)):
                if vol_ratio > VOL_MULT:
                    target = "CE" if trend == "BULLISH" else "PE"
                    sym = f"NSE-NIFTY-{OPT_EXPIRY_STR}-{int(round(fut['close']/50)*50)}-{target}"
                    if sym in self.option_cache and ts in self.option_cache[sym].index:
                        opt = self.option_cache[sym].loc[ts]
                        if opt['panic'] < OI_DROP:
                            pos, active_sym, entry_p, entry_t = target, sym, opt['close'], ts
                            sl_p, high_p = entry_p - SL_POINTS, entry_p

            # 4. Exit Logic
            elif pos:
                opt = self.option_cache[active_sym].loc[ts]
                if opt['close'] > high_p:
                    high_p = opt['close']
                    if (high_p - entry_p) > TRAIL_TRIG: sl_p = max(sl_p, high_p - TRAIL_GAP)
                if opt['low'] <= sl_p:
                    pnl = (sl_p - entry_p) * LOT_SIZE
                    bal += pnl
                    trades.append({'Entry': entry_t, 'Exit': ts, 'Sym': active_sym, 'Buy': entry_p, 'Sell': sl_p, 'PnL': pnl, 'Reason': 'SL'})
                    pos = None

        # --- TRADE BOOK DISPLAY ---
        df_book = pd.DataFrame(trades)
        print("\n" + "="*95)
        print(f"{'ENTRY TIME':<20} | {'SYMBOL':<25} | {'BUY':<7} | {'SELL':<7} | {'PnL':<10} | {'WHY'}")
        print("-" * 95)
        for _, r in df_book.iterrows():
            print(f"{str(r['Entry']):<20} | {r['Sym']:<25} | {r['Buy']:<7.1f} | {r['Sell']:<7.1f} | {r['PnL']:<10.1f} | {r['Reason']}")
        
        print("="*95)
        print(f"FINAL BALANCE: {bal:.2f} | TOTAL PnL: {bal-START_BAL:.2f} | WIN RATE: {(len(df_book[df_book['PnL']>0])/len(df_book)*100):.1f}%")

if __name__ == "__main__":
    BacktesterV91().run()