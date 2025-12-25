import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
INITIAL_CAPITAL = 10000
DAILY_LOSS_LIMIT = 1000  # ₹1,000 (10% of capital) 
RISK_PER_TRADE = 500     # ₹500 (approx 10 pts on premium) [cite: 248]
LOT_SIZE = 75            # Nifty Lot Size [cite: 98, 100]

class BacktestEngine:
    def __init__(self):
        # Authentication (API Key/Secret Flow) [cite: 1530]
        self.access_token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        self.groww = GrowwAPI(self.access_token)
        
        # CSV Logging Setup
        self.movement_file = "bot_movement_log.csv"
        self.tradebook_file = "tradebook.csv"
        self.init_csvs()

    def init_csvs(self):
        # Create headers for the logs
        pd.DataFrame(columns=["Timestamp", "Nifty_Price", "VWAP", "EMA9", "RSI", "OI_Change", "Action", "Reason"]).to_csv(self.movement_file, index=False)
        pd.DataFrame(columns=["Entry_Time", "Exit_Time", "Symbol", "Entry_Price", "Exit_Price", "Quantity", "PnL", "Result"]).to_csv(self.tradebook_file, index=False)

    def log_movement(self, data):
        pd.DataFrame([data]).to_csv(self.movement_file, mode='a', header=False, index=False)

    def log_trade(self, data):
        pd.DataFrame([data]).to_csv(self.tradebook_file, mode='a', header=False, index=False)

    def calculate_indicators(self, df):
        # Core Scalping Indicators [cite: 148, 160, 168]
        df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        # RSI Calculation (Window 14) [cite: 168, 287]
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        return df

    def run_backtest(self, symbol, start_date, end_date):
        # 1. Fetch Historical Data [cite: 2521, 2533]
        print(f"Fetching data for {symbol}...")
        raw_data = self.groww.get_historical_candles(
            exchange="NSE",
            segment="FNO", # For options backtesting [cite: 2525, 2536]
            groww_symbol=symbol,
            start_time=start_date,
            end_time=end_date,
            candle_interval="5minute" # 5-min timeframe as requested [cite: 88, 178]
        )
        
        # [timestamp, open, high, low, close, volume, open_interest] [cite: 2590]
        df = pd.DataFrame(raw_data['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
        df = self.calculate_indicators(df)
        
        in_position = False
        entry_data = {}

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            oi_change = row['oi'] - prev_row['oi']
            
            # Logic: Short Covering Momentum Burst (Strategy 1) [cite: 179, 184]
            # Criteria: Close > VWAP & 9 EMA, RSI > 60, OI is DROPPING [cite: 11, 116, 173, 183]
            buy_signal = (row['close'] > row['VWAP'] and 
                          row['close'] > row['EMA9'] and 
                          row['RSI'] > 60 and 
                          oi_change < 0)

            if not in_position:
                reason = "Waiting for setup"
                action = "SCANNING"
                
                if buy_signal:
                    in_position = True
                    entry_data = {
                        "Entry_Time": row['time'],
                        "Symbol": symbol,
                        "Entry_Price": row['close'],
                        "Quantity": LOT_SIZE
                    }
                    action = "BUY"
                    reason = "Short Covering Detected (OI Down + RSI > 60)"
                
                self.log_movement([row['time'], row['close'], round(row['VWAP'], 2), round(row['EMA9'], 2), round(row['RSI'], 2), oi_change, action, reason])
            
            else:
                # Exit Logic: 20 pt Target or 10 pt Stop Loss [cite: 189, 288]
                pnl_points = row['close'] - entry_data['Entry_Price']
                exit_signal = False
                exit_reason = ""

                if pnl_points >= 20:
                    exit_signal = True
                    exit_reason = "Target Hit (+20 pts)"
                elif pnl_points <= -10:
                    exit_signal = True
                    exit_reason = "Stop Loss Hit (-10 pts)"
                elif i == len(df) - 1:
                    exit_signal = True
                    exit_reason = "EOD Square-off"

                if exit_signal:
                    total_pnl = pnl_points * LOT_SIZE
                    self.log_trade([
                        entry_data['Entry_Time'], row['time'], symbol, 
                        entry_data['Entry_Price'], row['close'], LOT_SIZE, total_pnl, exit_reason
                    ])
                    self.log_movement([row['time'], row['close'], "-", "-", "-", "-", "EXIT", exit_reason])
                    in_position = False

        print("Backtest Complete. Check bot_movement_log.csv and tradebook.csv")

# EXECUTION
engine = BacktestEngine()
# Example: Nifty 24500 Call for last 5 days
engine.run_backtest("NSE-NIFTY-26Dec25-24500-CE", "2025-12-15 09:15:00", "2025-12-19 15:30:00")