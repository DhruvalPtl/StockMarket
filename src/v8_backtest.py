import pandas as pd
import numpy as np
import warnings
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys

# Suppress warnings
warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# ⚙️ V8 CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# RISK MANAGEMENT
CAPITAL        = 10000.0
LOT_SIZE       = 75
TARGET_POINTS  = 10.0     # Fixed Profit Target
SL_POINTS      = 10.0     # Fixed Stop Loss

# REVERSAL SETTINGS
RSI_PERIOD     = 14
RSI_OVERBOUGHT = 70       # Short when crossing below this
RSI_OVERSOLD   = 30       # Buy when crossing above this

# SYMBOLS (Proxies for Backtesting)
SPOT_SYMBOL = "NSE-NIFTY"
# We fetch both CE and PE to trade both sides
OPT_CE_SYMBOL = "NSE-NIFTY-23Dec25-26000-CE" 
OPT_PE_SYMBOL = "NSE-NIFTY-23Dec25-26000-PE" 

# FILES
LOG_FILE       = "V8_BOT_MOVEMENT.csv"
TRADE_FILE     = "V8_TRADEBOOK.csv"

class ReversalScalperV8:
    def __init__(self):
        print("--- V8: REVERSAL SCALPER (CE & PE) ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
            self.init_logs()
        except Exception as e:
            print(f"❌ Login Failed: {e}"); sys.exit()

    def init_logs(self):
        mov_cols = ["Time", "Spot_LTP", "RSI_5M", "Action_Zone", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(LOG_FILE, index=False)
        
        trd_cols = ["Entry_Time", "Exit_Time", "Instrument", "Type", "Entry_Price", "Exit_Price", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(TRADE_FILE, index=False)

    def log_movement(self, time, spot, rsi, zone, status, reason):
        data = {
            "Time": time, "Spot_LTP": spot, "RSI_5M": int(rsi), 
            "Action_Zone": zone, "Status": status, "Reason": reason
        }
        pd.DataFrame([data]).to_csv(LOG_FILE, mode='a', header=False, index=False)

    def log_trade(self, entry_t, exit_t, instr, type_, entry_p, exit_p, pnl, bal, reason):
        data = {
            "Entry_Time": entry_t, "Exit_Time": exit_t, "Instrument": instr, "Type": type_,
            "Entry_Price": entry_p, "Exit_Price": exit_p, 
            "PnL": round(pnl, 2), "Balance": round(bal, 2), "Reason": reason
        }
        pd.DataFrame([data]).to_csv(TRADE_FILE, mode='a', header=False, index=False)

    def fetch_and_clean(self, symbol, name):
        print(f"📥 Fetching 1-Min Data for {name}...")
        end = datetime.now()
        start = end - timedelta(days=5)
        
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO" if "CE" in symbol or "PE" in symbol else "CASH",
                symbol,
                start.strftime("%Y-%m-%d 09:15:00"),
                end.strftime("%Y-%m-%d 15:30:00"),
                "1minute"
            )
            
            if not resp or 'candles' not in resp: return None
            
            df = pd.DataFrame(resp['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            df['time'] = pd.to_datetime(df['time'])
            
            # Forward Fill to fix API gaps
            df['close'] = df['close'].ffill()
            df['high'] = df['high'].ffill()
            df['low'] = df['low'].ffill()
            
            return df
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def prepare_data(self):
        # 1. Fetch
        spot = self.fetch_and_clean(SPOT_SYMBOL, "SPOT")
        ce   = self.fetch_and_clean(OPT_CE_SYMBOL, "CALL OPTION")
        pe   = self.fetch_and_clean(OPT_PE_SYMBOL, "PUT OPTION")
        
        if spot is None or ce is None or pe is None:
            print("❌ Critical: Data Missing.")
            return None

        # 2. Merge all into one Master DataFrame
        # Rename columns to avoid collision
        spot = spot[['time', 'close']].rename(columns={'close': 'close_SPOT'})
        ce = ce[['time', 'close']].rename(columns={'close': 'close_CE'})
        pe = pe[['time', 'close']].rename(columns={'close': 'close_PE'})

        print("🔄 Merging Data Streams...")
        merged = pd.merge(spot, ce, on='time', how='inner')
        merged = pd.merge(merged, pe, on='time', how='inner')

        # 3. Calculate 5-Min RSI (The Trigger)
        print("📊 Calculating 5-Min RSI...")
        df_5m = merged.set_index('time').resample('5min').agg({'close_SPOT': 'last'}).dropna()
        
        delta = df_5m['close_SPOT'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        df_5m['RSI_5M'] = 100 - (100 / (1 + rs))

        # 4. Map 5-Min RSI back to 1-Min Data
        final_df = pd.merge_asof(
            merged.sort_values('time'), 
            df_5m[['RSI_5M']], 
            left_on='time', 
            right_index=True, 
            direction='backward'
        )
        
        return final_df.dropna()

    def run(self):
        df = self.prepare_data()
        if df is None: return

        balance = CAPITAL
        in_trade = False
        trade_data = {}
        
        print(f"🚀 Running Reversal Logic on {len(df)} candles...")
        
        # Start loop
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            t = row['time']
            spot = row['close_SPOT']
            rsi = row['RSI_5M']
            prev_rsi = prev_row['RSI_5M']
            
            # Time Filter (09:30 - 15:00)
            if not (930 <= (t.hour * 100 + t.minute) <= 1500):
                continue

            # -----------------------------
            # LOGIC: RSI CROSSOVER
            # -----------------------------
            if not in_trade:
                # 1. BULLISH REVERSAL (Buy CE)
                # Logic: RSI was below 30, now crossing ABOVE 30
                buy_signal = (prev_rsi < RSI_OVERSOLD) and (rsi >= RSI_OVERSOLD)
                
                # 2. BEARISH REVERSAL (Buy PE)
                # Logic: RSI was above 70, now crossing BELOW 70
                sell_signal = (prev_rsi > RSI_OVERBOUGHT) and (rsi <= RSI_OVERBOUGHT)

                if buy_signal:
                    price = row['close_CE']
                    if price * LOT_SIZE <= balance:
                        in_trade = True
                        trade_data = {
                            'entry_time': t, 'instr': 'CE', 'entry_price': price,
                            'target': price + TARGET_POINTS, 'sl': price - SL_POINTS
                        }
                        print(f"🟢 [CALL] Oversold Bounce @ {t.strftime('%H:%M')} | RSI: {int(rsi)}")
                        self.log_movement(t, spot, rsi, "Oversold", "BUY CE", "RSI Cross > 30")
                
                elif sell_signal:
                    price = row['close_PE']
                    if price * LOT_SIZE <= balance:
                        in_trade = True
                        trade_data = {
                            'entry_time': t, 'instr': 'PE', 'entry_price': price,
                            'target': price + TARGET_POINTS, 'sl': price - SL_POINTS
                        }
                        print(f"🔴 [PUT] Overbought Dump @ {t.strftime('%H:%M')} | RSI: {int(rsi)}")
                        self.log_movement(t, spot, rsi, "Overbought", "BUY PE", "RSI Cross < 70")
                
                else:
                    status = "SCAN"
                    zone = "Neutral"
                    if rsi > 70: zone = "Overbought (Waiting for dip)"
                    elif rsi < 30: zone = "Oversold (Waiting for bounce)"
                    self.log_movement(t, spot, rsi, zone, status, "Waiting for Cross")

            # -----------------------------
            # TRADE MANAGEMENT (Fixed Target/SL)
            # -----------------------------
            elif in_trade:
                # Get current price of the active instrument
                curr_price = row['close_CE'] if trade_data['instr'] == 'CE' else row['close_PE']
                
                exit_reason = None
                if curr_price >= trade_data['target']: exit_reason = "Target Hit"
                elif curr_price <= trade_data['sl']: exit_reason = "SL Hit"
                elif t.hour == 15: exit_reason = "EOD Exit"
                
                if exit_reason:
                    pnl = (curr_price - trade_data['entry_price']) * LOT_SIZE
                    balance += pnl
                    print(f"   -> CLOSED {trade_data['instr']} @ {curr_price} | PnL: {pnl:.2f} ({exit_reason})")
                    self.log_trade(trade_data['entry_time'], t, trade_data['instr'], "BUY", 
                                   trade_data['entry_price'], curr_price, pnl, balance, exit_reason)
                    in_trade = False
                else:
                    self.log_movement(t, spot, rsi, "In Trade", "HOLD", f"PnL: {(curr_price - trade_data['entry_price']) * LOT_SIZE:.0f}")

        print(f"\n✅ Simulation Complete.")
        print(f"👉 Check {LOG_FILE} and {TRADE_FILE}")

if __name__ == "__main__":
    ReversalScalperV8().run()