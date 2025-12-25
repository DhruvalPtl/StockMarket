import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta

# --- V2 CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
# FIX: Use FUTURES Symbol to get OI Data (Cash Index has no OI)
BACKTEST_SYMBOL = "NSE-NIFTY-26Dec25-FUT" 
INITIAL_BALANCE = 10000
LOT_SIZE = 75

# Trailing SL Settings
INITIAL_SL_OFFSET = 8
TRAIL_TRIGGER = 10
TRAIL_GAP = 5

class NiftyV2Fixed:
    def __init__(self):
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("Login Successful.")
        except Exception as e:
            print(f"Login Error: {e}")
            
        self.balance = INITIAL_BALANCE
        self.mov_file = "V2_BOT_MOVEMENT.csv"
        self.trade_file = "V2_TRADEBOOK.csv"
        self.init_logs()

    def init_logs(self):
        mov_cols = ["Timestamp", "Price", "VWAP", "EMA5", "EMA13", "OI", "OI_Chg", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(self.mov_file, index=False)
        
        trd_cols = ["Time_Entry", "Time_Exit", "Entry_Px", "Exit_Px", "Max_Px", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(self.trade_file, index=False)

    def run_v2_backtest(self):
        print(f"Fetching 1-min data for {BACKTEST_SYMBOL}...")
        
        # FIX: Segment changed to FNO to get Open Interest
        raw = self.groww.get_historical_candles(
            exchange="NSE", 
            segment="FNO", 
            groww_symbol=BACKTEST_SYMBOL,
            start_time="2025-12-15 09:15:00", 
            end_time="2025-12-19 15:30:00", 
            candle_interval="1minute"
        )
        
        if not raw or 'candles' not in raw:
            print("Error: No data fetched. Check Symbol or API Key.")
            return

        # Columns: [time, open, high, low, close, volume, oi]
        df = pd.DataFrame(raw['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        
        # Data Cleaning: Replace None OI with 0 to prevent crash
        df['oi'] = df['oi'].fillna(0)
        
        # Indicators
        df['EMA5'] = df['close'].ewm(span=5).mean()
        df['EMA13'] = df['close'].ewm(span=13).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        in_pos = False
        trade = {}

        # Loop starting at 13 to have enough data for EMA13
        for i in range(13, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Calculate OI Change (Now valid because we use Futures)
            oi_chg = row['oi'] - prev_row['oi']
            
            # --- STRATEGY LOGIC ---
            # 1. Trend: Price > VWAP & EMA13
            # 2. Trigger: Price crosses EMA5
            # 3. Confirmation: OI Drops (Short Covering)
            
            trend_ok = row['close'] > row['VWAP'] and row['close'] > row['EMA13']
            trigger_ok = row['close'] > row['EMA5']
            oi_ok = oi_chg < 0 # Short Covering
            
            entry_signal = trend_ok and trigger_ok and oi_ok

            if not in_pos:
                status = "SCANNING"
                reason = "Waiting"
                
                if entry_signal:
                    in_pos = True
                    # Simulation: Buying ATM Option (Price proxy = Future Price)
                    trade = {
                        "Time_Entry": row['time'],
                        "Entry_Px": row['close'], # Using Future Px as proxy for trend entry
                        "Max_Px": row['close'],
                        "SL": row['close'] - INITIAL_SL_OFFSET,
                        "Sim_Option_Entry": 100 # Assuming Rs 100 premium
                    }
                    status = "BUY"
                    reason = f"OI Drop: {oi_chg}"
                    print(f"[{row['time']}] BUY SIGNAL at {row['close']} | OI Chg: {oi_chg}")

                self.log_mov([row['time'], row['close'], round(row['VWAP'],1), round(row['EMA5'],1), 
                              round(row['EMA13'],1), row['oi'], oi_chg, status, reason])
            
            else:
                # Track Trade
                current_px = row['close']
                trade['Max_Px'] = max(trade['Max_Price'], current_px) if 'Max_Price' in trade else current_px
                
                # Trailing SL Logic
                profit = current_px - trade['Entry_Px']
                if profit >= TRAIL_TRIGGER:
                    new_sl = trade['Max_Px'] - TRAIL_GAP
                    if new_sl > trade['SL']:
                        trade['SL'] = new_sl
                        print(f"[{row['time']}] SL Trailed to {trade['SL']}")

                # Exit Logic
                exit_reason = ""
                if current_px <= trade['SL']: exit_reason = "SL Hit"
                elif i == len(df)-1: exit_reason = "EOD"

                if exit_reason:
                    # Calculate PnL (Simulated 0.5 Delta)
                    points_captured = current_px - trade['Entry_Px']
                    pnl = points_captured * 0.5 * LOT_SIZE # Delta 0.5
                    
                    self.balance += pnl
                    self.log_trade([trade['Time_Entry'], row['time'], trade['Entry_Px'], current_px, 
                                   trade['Max_Px'], pnl, self.balance, exit_reason])
                    in_pos = False
                    print(f"[{row['time']}] EXIT ({exit_reason}) PnL: {pnl}")

    def log_mov(self, data): pd.DataFrame([data]).to_csv(self.mov_file, mode='a', header=False, index=False)
    def log_trade(self, data): pd.DataFrame([data]).to_csv(self.trade_file, mode='a', header=False, index=False)

# Run
bot = NiftyV2Fixed()
bot.run_v2_backtest()