import pandas as pd
from growwapi import GrowwAPI
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
SYMBOL = "NSE-NIFTY-30Dec25-26000-CE" 
LOT_SIZE = 75

# Trailing SL Config
INITIAL_SL = 8      # 8 points hard stop
TRAIL_TRIGGER = 10  # Start trailing after 10 points profit
TRAIL_GAP = 5       # Keep SL 5 points below the peak price

class NiftyV1:
    def __init__(self):
        # 1. Login & Diagnosis
        try:
            self.access_token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(self.access_token)
            self.debug("V1_DEBUG: Login Successful.")
        except Exception as e:
            self.debug(f"V1_DEBUG ERROR: Login Failed - {e}")
        
        # 2. File Setup
        self.mov_file = "V1_BOT_MOVEMENT.csv"
        self.trade_file = "V1_TRADEBOOK.csv"
        self.init_csvs()

    def debug(self, msg):
        with open("V1_DEBUG.log", "a") as f:
            f.write(f"{datetime.now()}: {msg}\n")

    def init_csvs(self):
        pd.DataFrame(columns=["Time", "Px", "VWAP", "EMA9", "RSI", "OI_Chg", "Action", "Reason"]).to_csv(self.mov_file, index=False)
        pd.DataFrame(columns=["EntryTime", "ExitTime", "EntryPx", "ExitPx", "PnL", "ExitType"]).to_csv(self.trade_file, index=False)

    def run_v1(self):
        # Fetching Last Week (Dec 15 - Dec 19)
        data = self.groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=SYMBOL,
            start_time="2025-12-15 09:15:00", end_time="2025-12-19 15:30:00", candle_interval="5minute"
        )
        
        if not data['candles']:
            self.debug("V1_DEBUG ERROR: No data found. check symbol format.")
            return

        df = pd.DataFrame(data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        # Indicators
        df['EMA9'] = df['close'].ewm(span=9).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        in_pos = False
        entry_px, peak_px, current_sl, entry_time = 0, 0, 0, ""

        for i in range(1, len(df)):
            r = df.iloc[i]
            oi_chg = r['oi'] - df.iloc[i-1]['oi']
            
            # Entry Logic
            if not in_pos:
                # V1 Condition: Trend + Speed + Short Covering
                if r['close'] > r['VWAP'] and r['close'] > r['EMA9'] and oi_chg < 0:
                    in_pos, entry_px, peak_px, entry_time = True, r['close'], r['close'], r['time']
                    current_sl = entry_px - INITIAL_SL
                    self.log_mov(r, oi_chg, "BUY", "Short Covering Detected")
                else:
                    self.log_mov(r, oi_chg, "SCAN", "No Setup")
            
            # Trailing SL Logic
            else:
                peak_px = max(peak_px, r['close'])
                profit = r['close'] - entry_px
                
                # Activate Trailing
                if profit >= TRAIL_TRIGGER:
                    new_sl = peak_px - TRAIL_GAP
                    if new_sl > current_sl:
                        current_sl = new_sl

                # Exit Checks
                exit_type = ""
                if r['close'] <= current_sl: exit_type = "SL Hit"
                elif i == len(df)-1: exit_type = "EOD"

                if exit_type:
                    pnl = (r['close'] - entry_px) * LOT_SIZE
                    self.log_trade(entry_time, r['time'], entry_px, r['close'], pnl, exit_type)
                    in_pos = False

    def log_mov(self, r, oi, act, res):
        pd.DataFrame([[r['time'], r['close'], round(r['VWAP'], 1), round(r['EMA9'], 1), 0, oi, act, res]]).to_csv(self.mov_file, mode='a', header=False, index=False)

    def log_trade(self, et, xt, ep, xp, pnl, res):
        pd.DataFrame([[et, xt, ep, xp, pnl, res]]).to_csv(self.trade_file, mode='a', header=False, index=False)

bot = NiftyV1()
bot.run_v1()