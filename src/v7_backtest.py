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
# ⚙️ CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# STRATEGY PARAMETERS
CAPITAL        = 10000.0
LOT_SIZE       = 75
SL_POINTS      = 5.0     
TRAIL_TRIGGER  = 2.0     
TRAIL_GAP      = 2.0      
BUFFER_POINTS  = 3.0      # Trend Buffer (Price > EMA13 + 5)
RSI_THRESHOLD  = 50.0     

# SYMBOLS (Using the ones you verified)
SPOT_SYMBOL = "NSE-NIFTY"
FUT_SYMBOL  = "NSE-NIFTY-30Dec25-FUT"    
OPT_SYMBOL  = "NSE-NIFTY-23Dec25-26000-CE" 

# FILES
LOG_FILE       = "V7_BOT_MOVEMENT_s2.csv"
TRADE_FILE     = "V7_TRADEBOOK_s2.csv"

class InstitutionalSniperV7:
    def __init__(self):
        print("--- V7: DIRECT API BACKTESTER ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
            self.init_logs()
        except Exception as e:
            print(f"❌ Login Failed: {e}"); sys.exit()

    def init_logs(self):
        # 1. Movement Log
        mov_cols = ["Time", "Spot_LTP", "EMA13_Trend", "RSI", "Fut_LTP", "VWAP", "OI_Chg", "Status", "Reason"]
        pd.DataFrame(columns=mov_cols).to_csv(LOG_FILE, index=False)
        
        # 2. Trade Log
        trd_cols = ["Entry_Time", "Exit_Time", "Type", "Entry_Price", "Exit_Price", "PnL", "Balance", "Reason"]
        pd.DataFrame(columns=trd_cols).to_csv(TRADE_FILE, index=False)

    def log_movement(self, time, spot, ema13, rsi, fut, vwap, oi_chg, status, reason):
        data = {
            "Time": time, "Spot_LTP": spot, "EMA13_Trend": round(ema13, 2), "RSI": int(rsi),
            "Fut_LTP": fut, "VWAP": round(vwap, 2), "OI_Chg": int(oi_chg), 
            "Status": status, "Reason": reason
        }
        pd.DataFrame([data]).to_csv(LOG_FILE, mode='a', header=False, index=False)

    def log_trade(self, entry_t, exit_t, type_, entry_p, exit_p, pnl, bal, reason):
        data = {
            "Entry_Time": entry_t, "Exit_Time": exit_t, "Type": type_,
            "Entry_Price": entry_p, "Exit_Price": exit_p, 
            "PnL": round(pnl, 2), "Balance": round(bal, 2), "Reason": reason
        }
        pd.DataFrame([data]).to_csv(TRADE_FILE, mode='a', header=False, index=False)

    def fetch_and_clean(self, symbol, name):
        """Fetches 1-Min Data & Applies 'Smart Fill' Logic (Part 1 Logic)"""
        print(f"📥 Fetching 1-Min Data for {name} ({symbol})...")
        end = datetime.now()
        start = end - timedelta(days=30)
        
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO" if "FUT" in symbol or "CE" in symbol else "CASH",
                symbol,
                start.strftime("%Y-%m-%d 09:15:00"),
                end.strftime("%Y-%m-%d 15:30:00"),
                "1minute"
            )
            
            if not resp or 'candles' not in resp: return None
            
            df = pd.DataFrame(resp['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            df['time'] = pd.to_datetime(df['time'])
            
            # --- DATA CLEANING (The Fix) ---
            # Forward Fill to handle zeros/gaps in API data
            df['close'] = df['close'].ffill()
            df['high'] = df['high'].ffill()
            df['low'] = df['low'].ffill()
            
            if 'oi' in df.columns:
                df['oi'] = df['oi'].ffill()
                df['oi'] = df['oi'].fillna(0)
            else:
                df['oi'] = 0
                
            return df
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def calculate_vwap(self, df):
        """Calculates VWAP on Futures (Resets Daily)"""
        df['date'] = df['time'].dt.date
        
        # Vectorized VWAP calculation
        df['pv'] = df['volume_FUT'] * (df['high_FUT'] + df['low_FUT'] + df['close_FUT']) / 3
        df['cum_pv'] = df.groupby('date')['pv'].cumsum()
        df['cum_vol'] = df.groupby('date')['volume_FUT'].cumsum()
        
        return df['cum_pv'] / df['cum_vol']

    def prepare_data(self):
        # 1. Fetch Raw Data
        spot = self.fetch_and_clean(SPOT_SYMBOL, "SPOT")
        fut = self.fetch_and_clean(FUT_SYMBOL, "FUTURES")
        opt = self.fetch_and_clean(OPT_SYMBOL, "OPTION")
        
        if spot is None or fut is None or opt is None:
            print("❌ Critical: Data Missing.")
            return None

        # 2. Rename Columns
        spot = spot[['time', 'close']].rename(columns={'close': 'close_SPOT'})
        fut = fut.rename(columns={'close':'close_FUT', 'high':'high_FUT', 'low':'low_FUT', 'volume':'volume_FUT', 'oi':'oi_FUT'})
        opt = opt[['time', 'close']].rename(columns={'close':'close_OPT'})

        # 3. Merge (Inner Join)
        print("🔄 Merging & Processing...")
        merged = pd.merge(spot, fut[['time','close_FUT','high_FUT','low_FUT','volume_FUT','oi_FUT']], on='time')
        merged = pd.merge(merged, opt, on='time')

        # 4. Indicators
        merged['VWAP_FUT'] = self.calculate_vwap(merged)
        merged['OI_CHG'] = merged['oi_FUT'].diff().fillna(0)

        # 5. Virtual 5-Min Trend Indicators
        print("📊 Calculating 5-Min Trend Indicators...")
        df_5m = merged.set_index('time').resample('5min').agg({
            'close_SPOT': 'last'
        }).dropna()

        # EMA 13 (Trend) on 5-Min
        df_5m['EMA13_5M'] = df_5m['close_SPOT'].ewm(span=13, adjust=False).mean()
        
        # RSI 14 on 5-Min
        delta = df_5m['close_SPOT'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df_5m['RSI_5M'] = 100 - (100 / (1 + rs))

        # 6. Map 5-Min Trend back to 1-Min Data
        final_df = pd.merge_asof(
            merged.sort_values('time'), 
            df_5m[['EMA13_5M', 'RSI_5M']], 
            left_on='time', 
            right_index=True, 
            direction='backward'
        )
        
        # 7. EMA 5 (Fast Trigger) on 1-Min
        final_df['EMA5_1M'] = final_df['close_SPOT'].ewm(span=5, adjust=False).mean()
        
        return final_df.dropna()

    def run(self):
        df = self.prepare_data()
        if df is None: return

        balance = CAPITAL
        in_trade = False
        trade_data = {}
        
        print(f"🚀 Running Sniper Logic on {len(df)} candles...")
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            
            # Data
            t = row['time']
            spot = row['close_SPOT']
            fut = row['close_FUT']
            vwap = row['VWAP_FUT']
            oi_chg = row['OI_CHG']
            opt = row['close_OPT']
            
            # Indicators
            ema13 = row['EMA13_5M']
            ema5 = row['EMA5_1M']
            rsi = row['RSI_5M']
            
            # Time Filter
            if not (930 <= (t.hour * 100 + t.minute) <= 1500):
                continue

            # -----------------------------
            # LOGIC ENGINE
            # -----------------------------
            if not in_trade:
                # 1. Trend Check
                trend_ok = (spot > (ema13 + BUFFER_POINTS)) and (rsi > RSI_THRESHOLD)
                
                # 2. Institutional Check
                inst_ok = fut > vwap
                
                # 3. Trigger (Price > EMA5)
                trigger_ok = spot > ema5
                
                # 4. Confirmation (Short Covering)
                confirm_ok = oi_chg < 0
                
                if trend_ok and inst_ok and trigger_ok and confirm_ok:
                    # Budget Check
                    if opt * LOT_SIZE <= balance:
                        in_trade = True
                        trade_data = {
                            'entry_time': t, 'entry_price': opt, 
                            'sl': opt - SL_POINTS, 'peak': opt
                        }
                        print(f"🟢 BUY @ {t.strftime('%H:%M')} | Price: {opt} | Spot: {spot}")
                        self.log_movement(t, spot, ema13, rsi, fut, vwap, oi_chg, "BUY", "Setup Found")
                    else:
                        self.log_movement(t, spot, ema13, rsi, fut, vwap, oi_chg, "SKIP", "Over Budget")
                else:
                    # Logging Reasons
                    reason = "Waiting"
                    if not trend_ok: reason = f"Trend Weak (Spot vs EMA13+{int(BUFFER_POINTS)} or RSI {int(rsi)})"
                    elif not inst_ok: reason = "Below VWAP"
                    elif not confirm_ok: reason = "No Short Covering"
                    
                    self.log_movement(t, spot, ema13, rsi, fut, vwap, oi_chg, "SCAN", reason)
            
            # -----------------------------
            # TRADE MANAGEMENT
            # -----------------------------
            elif in_trade:
                # Update Peak
                if opt > trade_data['peak']: trade_data['peak'] = opt
                
                # Update Trailing SL
                if (trade_data['peak'] - trade_data['entry_price']) >= TRAIL_TRIGGER:
                    new_sl = trade_data['peak'] - TRAIL_GAP
                    if new_sl > trade_data['sl']: trade_data['sl'] = new_sl
                
                # Check Exit
                reason = None
                if opt <= trade_data['sl']: reason = "SL Hit"
                elif t.hour == 15: reason = "EOD Exit"
                
                if reason:
                    pnl = (opt - trade_data['entry_price']) * LOT_SIZE
                    balance += pnl
                    print(f"🔴 SELL @ {t.strftime('%H:%M')} | Price: {opt} | PnL: {pnl:.2f} ({reason})")
                    self.log_trade(trade_data['entry_time'], t, "BUY", trade_data['entry_price'], opt, pnl, balance, reason)
                    in_trade = False
                else:
                    self.log_movement(t, spot, ema13, rsi, fut, vwap, oi_chg, "HOLD", f"PnL: {(opt - trade_data['entry_price']) * LOT_SIZE:.0f}")

        print(f"\n✅ Simulation Complete.")
        print(f"👉 Check {LOG_FILE} for frame-by-frame analysis.")
        print(f"👉 Check {TRADE_FILE} for trade results.")

if __name__ == "__main__":
    InstitutionalSniperV7().run()