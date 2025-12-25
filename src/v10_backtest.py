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
# ⚙️ V10 CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# TIME SETTINGS
DAYS_TO_TEST   = 5       # How many days back to test
END_DATE       = datetime.now()

# STRATEGY PARAMETERS
CAPITAL        = 10000.0
LOT_SIZE       = 75
TARGET_PTS     = 20.0    # Initial Target
FIXED_SL       = 4.0    # Hard Stop Loss
TRAIL_TRIGGER  = 3.0    # If profit hits this...
TRAIL_LOCK     = 3.0     # ...Move SL to Entry + 5
TIME_STOP_MINS = 200      # Force exit if stagnant

# INDICATORS
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30      # Buy Call Zone
RSI_OVERBOUGHT = 70      # Buy Put Zone

# SYMBOLS
SPOT_SYMBOL = "NSE-NIFTY"
# IMPORTANT: Update this if testing different months!
FUT_SYMBOL  = "NSE-NIFTY-30Dec25-FUT" 

# FILES
LOG_FILE   = "V10_BOT_MOVEMENT.csv"
TRADE_FILE = "V10_TRADEBOOK.csv"

class OnDemandBacktesterV10:
    def __init__(self):
        print("--- V10: ON-DEMAND ACCURACY ENGINE ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
            self.init_logs()
            self.expiries = self.get_all_expiries()
        except Exception as e:
            print(f"❌ Initialization Failed: {e}"); sys.exit()

    def init_logs(self):
        mov_cols = [
            "Timestamp", "Spot_Price", "Fut_Price", "VWAP", 
            "RSI", "OI_Fut", "OI_Chg_3min", "Status", "Action"
        ]
        pd.DataFrame(columns=mov_cols).to_csv(LOG_FILE, index=False)
        
        trd_cols = [
            "Entry_Time", "Exit_Time", "Symbol", "Type", 
            "Spot_Entry", "Spot_Exit", "Opt_Entry", "Opt_Exit",
            "PnL", "Balance", "Exit_Reason", "Duration_Mins"
        ]
        pd.DataFrame(columns=trd_cols).to_csv(TRADE_FILE, index=False)

    def get_all_expiries(self):
        try:
            resp = self.groww.get_expiries("NSE", "NIFTY")
            if 'expiries' in resp:
                return sorted([datetime.strptime(d, "%Y-%m-%d") for d in resp['expiries']])
        except: pass
        return []

    def get_weekly_expiry(self, current_date):
        for exp in self.expiries:
            if exp.date() >= current_date.date():
                return exp.strftime("%d%b%y")
        return None

    def fetch_ohlc(self, symbol, start, end):
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO" if "FUT" in symbol or "CE" in symbol or "PE" in symbol else "CASH",
                symbol, start, end, "1minute"
            )
            if not resp or 'candles' not in resp: return pd.DataFrame()
            df = pd.DataFrame(resp['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            df['time'] = pd.to_datetime(df['time'])
            
            # Clean Data (Forward Fill)
            df['close'] = df['close'].ffill()
            if 'oi' in df.columns: 
                df['oi'] = df['oi'].ffill().fillna(0)
            else: 
                df['oi'] = 0
            return df
        except: return pd.DataFrame()

    def calculate_indicators(self, df):
        # 1. VWAP on Futures
        df['pv'] = df['close_FUT'] * df['volume_FUT']
        df['VWAP'] = df['pv'].cumsum() / df['volume_FUT'].cumsum()
        
        # 2. RSI on Spot (5-Min Resampled)
        df_5m = df.set_index('time').resample('5min').agg({'close_SPOT': 'last'}).dropna()
        delta = df_5m['close_SPOT'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss
        df_5m['RSI'] = 100 - (100 / (1 + rs))
        
        # Map RSI back to 1-min
        df = pd.merge_asof(df.sort_values('time'), df_5m['RSI'], on='time', direction='backward')
        
        # 3. OI Change (Real 3-min diff)
        # We take diff and smooth it slightly to catch the "Step"
        df['OI_Chg'] = df['oi_FUT'].diff()
        
        return df

    def run_day(self, date_obj, start_bal):
        date_str = date_obj.strftime("%Y-%m-%d")
        start_t = f"{date_str} 09:15:00"
        end_t   = f"{date_str} 15:30:00"
        
        # 1. Fetch Backbone Data
        spot = self.fetch_ohlc(SPOT_SYMBOL, start_t, end_t)
        fut  = self.fetch_ohlc(FUT_SYMBOL, start_t, end_t)
        
        if spot.empty or fut.empty: return start_bal, []
        
        # Rename & Merge
        spot = spot[['time', 'close']].rename(columns={'close': 'close_SPOT'})
        fut  = fut[['time', 'close', 'volume', 'oi']].rename(columns={'close': 'close_FUT', 'volume': 'volume_FUT', 'oi': 'oi_FUT'})
        
        df = pd.merge(spot, fut, on='time')
        df = self.calculate_indicators(df)
        
        trades = []
        balance = start_bal
        in_trade = False
        trade_ctx = {} # Context for active trade
        
        # Expiry for this day
        expiry = self.get_weekly_expiry(date_obj)
        if not expiry: return balance, []

        log_buffer = []

        # LOOP THROUGH MINUTES
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            t = row['time']
            rsi = row['RSI'] if not np.isnan(row['RSI']) else 50
            prev_rsi = prev['RSI'] if not np.isnan(prev['RSI']) else 50
            
            # --- 1. SIGNAL SCANNING ---
            if not in_trade:
                # Time Rule
                if not (930 <= (t.hour*100 + t.minute) <= 1500): continue
                
                # Signals
                buy_call = (prev_rsi < RSI_OVERSOLD) and (rsi >= RSI_OVERSOLD)
                buy_put  = (prev_rsi > RSI_OVERBOUGHT) and (rsi <= RSI_OVERBOUGHT)
                
                if buy_call or buy_put:
                    # --- ON-DEMAND FETCHING ---
                    # 1. Identify Strike
                    atm = round(row['close_SPOT'] / 50) * 50
                    opt_type = "CE" if buy_call else "PE"
                    sym = f"NSE-NIFTY-{expiry}-{atm}-{opt_type}"
                    
                    # 2. Fetch Option Data (From NOW until End of Day)
                    opt_df = self.fetch_ohlc(sym, str(t), end_t)
                    
                    if not opt_df.empty:
                        entry_px = opt_df.iloc[0]['close']
                        
                        # Budget Check
                        if entry_px * LOT_SIZE <= balance:
                            # EXECUTE
                            in_trade = True
                            trade_ctx = {
                                'entry_t': t, 'sym': sym, 'type': opt_type,
                                'entry_p': entry_px, 'spot_entry': row['close_SPOT'],
                                'sl': entry_px - FIXED_SL, 'peak': entry_px,
                                'df': opt_df # Store specific option data
                            }
                            print(f"⚡ ACTION: {opt_type} {sym} @ {entry_px} (RSI {int(rsi)})")
                
                # Log Scan
                status = "SCAN"
                action = "Wait"
                if buy_call: action = "Signal CE (Checking...)"
                if buy_put: action = "Signal PE (Checking...)"
                
                log_buffer.append([t, row['close_SPOT'], row['close_FUT'], row['VWAP'], rsi, row['oi_FUT'], row['OI_Chg'], status, action])

            # --- 2. TRADE MANAGEMENT ---
            elif in_trade:
                # We need to find the current price in our 'trade_ctx["df"]'
                # Look for the row matching current time 't'
                opt_row = trade_ctx['df'][trade_ctx['df']['time'] == t]
                
                if not opt_row.empty:
                    curr_px = opt_row.iloc[0]['close']
                    
                    # Update Peak
                    if curr_px > trade_ctx['peak']: trade_ctx['peak'] = curr_px
                    
                    # Aggressive Trailing
                    profit = curr_px - trade_ctx['entry_p']
                    if profit >= TRAIL_TRIGGER:
                        # Lock Profit: Entry + 5
                        new_sl = trade_ctx['entry_p'] + TRAIL_LOCK
                        if new_sl > trade_ctx['sl']: trade_ctx['sl'] = new_sl

                    # Check Time Stop
                    duration = (t - trade_ctx['entry_t']).total_seconds() / 60
                    
                    exit_reason = None
                    if curr_px <= trade_ctx['sl']: exit_reason = "SL Hit"
                    elif duration >= TIME_STOP_MINS: exit_reason = "Time Stop (45m)"
                    elif t.hour == 15 and t.minute >= 20: exit_reason = "EOD Force"
                    
                    if exit_reason:
                        pnl = (curr_px - trade_ctx['entry_p']) * LOT_SIZE
                        balance += pnl
                        trades.append([
                            trade_ctx['entry_t'], t, trade_ctx['sym'], trade_ctx['type'],
                            trade_ctx['spot_entry'], row['close_SPOT'], 
                            trade_ctx['entry_p'], curr_px, pnl, balance, exit_reason, int(duration)
                        ])
                        print(f"   -> CLOSED {trade_ctx['type']} @ {curr_px} | PnL: {pnl:.2f} ({exit_reason})")
                        in_trade = False
                    
                    # Log Holding
                    log_buffer.append([t, row['close_SPOT'], row['close_FUT'], row['VWAP'], rsi, row['oi_FUT'], row['OI_Chg'], "HOLD", f"PnL: {profit*LOT_SIZE:.0f}"])

        # Flush Logs
        pd.DataFrame(log_buffer).to_csv(LOG_FILE, mode='a', header=False, index=False)
        pd.DataFrame(trades).to_csv(TRADE_FILE, mode='a', header=False, index=False)
        return balance, trades

    def run(self):
        print(f"🚀 V10 Engine Starting. Testing last {DAYS_TO_TEST} days...")
        curr_bal = CAPITAL
        
        for i in range(DAYS_TO_TEST, 0, -1):
            d = END_DATE - timedelta(days=i)
            if d.weekday() > 4: continue # Skip Weekends
            
            print(f"📅 Simulating {d.strftime('%Y-%m-%d')}...")
            curr_bal, _ = self.run_day(d, curr_bal)
            
        print("\n" + "="*60)
        print(f"FINAL BALANCE: {curr_bal:.2f}")
        print(f"NET PROFIT   : {curr_bal - CAPITAL:.2f}")

if __name__ == "__main__":
    OnDemandBacktesterV10().run()