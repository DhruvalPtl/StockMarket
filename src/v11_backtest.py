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
# ⚙️ V11 CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# TIME SETTINGS
DAYS_TO_TEST   = 5       # Days to backtest
END_DATE       = datetime.now()

# STRATEGY PARAMETERS
CAPITAL        = 10000.0
LOT_SIZE       = 75
FIXED_SL       = 4    # Initial Risk (Points)
TRAIL_TRIGGER  = 3    # Profit needed to activate trailing
TRAIL_LOCK     = 2     # Lock profit at Entry + 5
TIME_STOP_MINS = 200     # Exit if trade is stagnant

# INDICATORS
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30      # Buy Call Zone
RSI_OVERBOUGHT = 70      # Buy Put Zone

# SYMBOLS
SPOT_SYMBOL = "NSE-NIFTY"
FUT_SYMBOL  = "NSE-NIFTY-30Dec25-FUT" 

# FILES
LOG_FILE   = "V11_BOT_MOVEMENT.csv"
TRADE_FILE = "V11_TRADEBOOK.csv"

class PrecisionBacktesterV11:
    def __init__(self):
        print("--- V11: PRECISION EXECUTION ENGINE ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
            self.init_logs()
            self.expiries = self.get_all_expiries()
        except Exception as e:
            print(f"❌ Initialization Failed: {e}"); sys.exit()

    def init_logs(self):
        # 1. Enhanced Movement Log (With Strike & Prices)
        mov_cols = [
            "Timestamp", "Nifty_Price", "RSI", "Status", 
            "Strike_Selected", "CE_Price", "PE_Price", "Reason"
        ]
        pd.DataFrame(columns=mov_cols).to_csv(LOG_FILE, index=False)
        
        # 2. Enhanced Tradebook (With Max Price)
        trd_cols = [
            "Entry_Time", "Exit_Time", "Symbol", "Type", 
            "Entry_Price", "Exit_Price", "Max_Price_Reached", "Final_SL",
            "PnL", "Balance", "Exit_Reason"
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
            
            # Forward Fill
            df['close'] = df['close'].ffill()
            df['open'] = df['open'].fillna(df['close'])
            df['high'] = df['high'].fillna(df['close'])
            df['low'] = df['low'].fillna(df['close'])
            return df
        except: return pd.DataFrame()

    def calculate_indicators(self, df):
        # RSI on Spot (5-Min Resampled)
        df_5m = df.set_index('time').resample('5min').agg({'close_SPOT': 'last'}).dropna()
        delta = df_5m['close_SPOT'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss
        df_5m['RSI'] = 100 - (100 / (1 + rs))
        
        # Map RSI back to 1-min
        df = pd.merge_asof(df.sort_values('time'), df_5m['RSI'], on='time', direction='backward')
        return df

    def run_day(self, date_obj, start_bal):
        date_str = date_obj.strftime("%Y-%m-%d")
        start_t = f"{date_str} 09:15:00"
        end_t   = f"{date_str} 15:30:00"
        
        # 1. Fetch Spot Data
        spot = self.fetch_ohlc(SPOT_SYMBOL, start_t, end_t)
        if spot.empty: return start_bal, []
        
        spot = spot[['time', 'close']].rename(columns={'close': 'close_SPOT'})
        df = self.calculate_indicators(spot)
        
        trades = []
        balance = start_bal
        in_trade = False
        trade_ctx = {} 
        
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
            
            # Dynamic Strike
            atm = round(row['close_SPOT'] / 50) * 50
            ce_sym = f"NSE-NIFTY-{expiry}-{atm}-CE"
            pe_sym = f"NSE-NIFTY-{expiry}-{atm}-PE"
            
            # --- 1. SIGNAL SCANNING ---
            if not in_trade:
                if not (930 <= (t.hour*100 + t.minute) <= 1500): continue
                
                buy_call = (prev_rsi < RSI_OVERSOLD) and (rsi >= RSI_OVERSOLD)
                buy_put  = (prev_rsi > RSI_OVERBOUGHT) and (rsi <= RSI_OVERBOUGHT)
                
                ce_px, pe_px = 0, 0
                
                if buy_call or buy_put:
                    target_sym = ce_sym if buy_call else pe_sym
                    opt_df = self.fetch_ohlc(target_sym, str(t), end_t)
                    
                    if not opt_df.empty:
                        entry_px = opt_df.iloc[0]['close']
                        ce_px = entry_px if buy_call else 0
                        pe_px = entry_px if buy_put else 0
                        
                        if entry_px * LOT_SIZE <= balance:
                            in_trade = True
                            trade_ctx = {
                                'entry_t': t, 'sym': target_sym, 'type': 'CE' if buy_call else 'PE',
                                'entry_p': entry_px, 'sl': entry_px - FIXED_SL, 
                                'peak': entry_px, 'df': opt_df, 'sl_moved': False
                            }
                            print(f"⚡ ENTER: {trade_ctx['type']} @ {entry_px} (RSI {int(rsi)})")

                status = "SCAN"
                log_buffer.append([t, row['close_SPOT'], rsi, status, atm, ce_px, pe_px, "Wait"])

            # --- 2. PRECISION TRADE MANAGEMENT (LOW/HIGH CHECK) ---
            elif in_trade:
                opt_row = trade_ctx['df'][trade_ctx['df']['time'] == t]
                
                if not opt_row.empty:
                    # Get OHLC for Precision Execution
                    o = opt_row.iloc[0]['open']
                    h = opt_row.iloc[0]['high']
                    l = opt_row.iloc[0]['low']
                    c = opt_row.iloc[0]['close']
                    
                    # 1. CHECK SL HIT (Priority)
                    # Use LOW to see if SL was breached
                    exit_price = 0
                    exit_reason = None
                    
                    if l <= trade_ctx['sl']:
                        exit_reason = "SL Hit"
                        # Gap Down Logic: If Open is already below SL, we exit at Open
                        exit_price = o if o < trade_ctx['sl'] else trade_ctx['sl']
                    
                    # 2. CHECK TARGET / TRAILING (If SL not hit)
                    if not exit_reason:
                        # Update Peak using HIGH
                        if h > trade_ctx['peak']: trade_ctx['peak'] = h
                        
                        # Check if High triggered Trailing
                        profit_at_high = h - trade_ctx['entry_p']
                        
                        if profit_at_high >= TRAIL_TRIGGER and not trade_ctx['sl_moved']:
                            trade_ctx['sl'] = trade_ctx['entry_p'] + TRAIL_LOCK
                            trade_ctx['sl_moved'] = True
                            print(f"   🔒 Trailing Active! SL -> {trade_ctx['sl']}")
                        
                        # Time Stop
                        duration = (t - trade_ctx['entry_t']).total_seconds() / 60
                        if duration >= TIME_STOP_MINS: 
                            exit_reason = "Time Stop (45m)"
                            exit_price = c # Exit at Close for Time Stop
                        elif t.hour == 15 and t.minute >= 20: 
                            exit_reason = "EOD Force"
                            exit_price = c
                    
                    # 3. EXECUTE EXIT
                    if exit_reason:
                        pnl = (exit_price - trade_ctx['entry_p']) * LOT_SIZE
                        balance += pnl
                        trades.append([
                            trade_ctx['entry_t'], t, trade_ctx['sym'], trade_ctx['type'],
                            trade_ctx['entry_p'], exit_price, trade_ctx['peak'], trade_ctx['sl'],
                            pnl, balance, exit_reason
                        ])
                        print(f"   🔴 CLOSED {trade_ctx['type']} @ {exit_price} | PnL: {pnl:.2f} ({exit_reason})")
                        in_trade = False
                    
                    # Log Holding
                    log_buffer.append([t, row['close_SPOT'], rsi, "HOLD", atm, c, 0, f"PnL: {(c - trade_ctx['entry_p'])*LOT_SIZE:.0f}"])

        pd.DataFrame(log_buffer).to_csv(LOG_FILE, mode='a', header=False, index=False)
        pd.DataFrame(trades).to_csv(TRADE_FILE, mode='a', header=False, index=False)
        return balance, trades

    def run(self):
        print(f"🚀 V11 Precision Engine Starting...")
        curr_bal = CAPITAL
        for i in range(DAYS_TO_TEST, 0, -1):
            d = END_DATE - timedelta(days=i)
            if d.weekday() > 4: continue 
            print(f"📅 Simulating {d.strftime('%Y-%m-%d')}...")
            curr_bal, _ = self.run_day(d, curr_bal)
        print("\n" + "="*60)
        print(f"FINAL BALANCE: {curr_bal:.2f}")

if __name__ == "__main__":
    PrecisionBacktesterV11().run()