import pandas as pd
import numpy as np
import warnings
from growwapi import GrowwAPI
from datetime import datetime, timedelta, time
import sys
from scipy.stats import norm

# Suppress warnings
warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# ⚙️ V9 CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# TIME MACHINE SETTINGS
DAYS_TO_TEST   = 5       # Set to 30, 180, 365 for longer tests
END_DATE       = datetime.now() 

# STRATEGY PARAMETERS
CAPITAL        = 10000.0
LOT_SIZE       = 75
FIXED_SL       = 10.0    # Initial Stop Loss
TARGET_PTS     = 10.0    # Initial Target
TRAIL_ACTIVATE = 10.0    # Profit needed to move SL to Cost
TRAIL_GAP      = 5.0     # Trail gap after activation

# INDICATORS
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30      # Buy CE
RSI_OVERBOUGHT = 70      # Buy PE

# SYMBOLS
SPOT_SYMBOL = "NSE-NIFTY"
FUT_SYMBOL  = "NSE-NIFTY-30Dec25-FUT" # Note: For >1 month backtest, this needs to be dynamic too.
                                      # For now, we assume testing current month.

# FILES
LOG_FILE   = "V9_BOT_MOVEMENT.csv"
TRADE_FILE = "V9_TRADEBOOK.csv"

class BacktesterV9:
    def __init__(self):
        print("--- V9: THE TIME MACHINE (Reversal + Trailing + Greeks) ---")
        try:
            self.groww = GrowwAPI(GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET))
            print("✅ Login Successful.")
            self.init_logs()
            self.expiries = self.get_all_expiries()
        except Exception as e:
            print(f"❌ Initialization Failed: {e}"); sys.exit()

    def init_logs(self):
        # 1. Rich Bot Movement Log
        mov_cols = [
            "Timestamp", "Nifty_Price", "VWAP", "EMA5", "EMA13", 
            "Strike_Looking", "CE_Price", "PE_Price", 
            "OI_Fut", "OI_Chg", "PCR_Proxy", "Delta_Approx", 
            "RSI", "Action_Zone", "Status", "Reason"
        ]
        pd.DataFrame(columns=mov_cols).to_csv(LOG_FILE, index=False)
        
        # 2. Detailed Trade Book
        trd_cols = [
            "Entry_Time", "Exit_Time", "Symbol", "Type", 
            "Nifty_Entry", "Nifty_Exit", "Opt_Entry", "Opt_Exit",
            "Max_Price_Reached", "Trailing_SL_Price", "Final_SL",
            "PnL", "Balance", "Entry_Reason", "Exit_Reason"
        ]
        pd.DataFrame(columns=trd_cols).to_csv(TRADE_FILE, index=False)

    def get_all_expiries(self):
        """Fetches all Nifty expiries for mapping"""
        try:
            resp = self.groww.get_expiries("NSE", "NIFTY")
            if 'expiries' in resp:
                # Convert to datetime for easy comparison
                return sorted([datetime.strptime(d, "%Y-%m-%d") for d in resp['expiries']])
        except: pass
        return []

    def get_weekly_expiry(self, current_date):
        """Finds the next Thursday expiry for a given date"""
        for exp in self.expiries:
            if exp.date() >= current_date.date():
                return exp.strftime("%d%b%y") # Format: 23Dec25
        return None

    def calculate_greeks(self, spot, strike, time_to_expiry_days, type='CE'):
        """
        Simplified Black-Scholes Delta Approximation
        Note: Full Greeks require IV, which we don't have. 
        We use a standard estimation.
        """
        try:
            # Proxy Delta using Moneyness
            # Deep ITM -> 1.0, ATM -> 0.5, OTM -> 0.0
            moneyness = spot / strike
            if type == 'CE':
                if moneyness > 1.01: return 0.8  # ITM
                elif moneyness < 0.99: return 0.2 # OTM
                else: return 0.5 # ATM
            else: # PE
                if moneyness < 0.99: return -0.8 # ITM
                elif moneyness > 1.01: return -0.2 # OTM
                else: return -0.5 # ATM
        except: return 0

    def fetch_data(self, symbol, start, end):
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO" if "FUT" in symbol or "CE" in symbol or "PE" in symbol else "CASH",
                symbol, start, end, "1minute"
            )
            if not resp or 'candles' not in resp: return pd.DataFrame()
            df = pd.DataFrame(resp['candles'], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            df['time'] = pd.to_datetime(df['time'])
            
            # Smart Fill (Clean Data)
            df['close'] = df['close'].ffill()
            if 'oi' in df.columns: 
                df['oi'] = df['oi'].ffill().fillna(0)
            else: 
                df['oi'] = 0
            return df
        except: return pd.DataFrame()

    def process_daily_batch(self, date_start, balance):
        """
        Simulates ONE DAY of trading.
        Fetches Spot, Future, and specific ATM Options for that day.
        """
        date_end_str = (date_start + timedelta(days=1)).strftime("%Y-%m-%d 09:15:00")
        date_start_str = date_start.strftime("%Y-%m-%d 09:15:00")
        
        # 1. Fetch Spot & Futures (Backbone)
        spot_df = self.fetch_data(SPOT_SYMBOL, date_start_str, date_end_str)
        fut_df  = self.fetch_data(FUT_SYMBOL, date_start_str, date_end_str)
        
        if spot_df.empty: return balance, []

        # 2. Determine ATM Strike for the Day (Using 9:15 Open)
        day_open = spot_df.iloc[0]['open']
        atm_strike = round(day_open / 50) * 50
        
        # 3. Get Expiry & Symbols
        expiry_str = self.get_weekly_expiry(date_start)
        if not expiry_str: return balance, []
        
        ce_sym = f"NSE-NIFTY-{expiry_str}-{atm_strike}-CE"
        pe_sym = f"NSE-NIFTY-{expiry_str}-{atm_strike}-PE"
        
        # 4. Fetch Option Data (Only for this day)
        ce_df = self.fetch_data(ce_sym, date_start_str, date_end_str)
        pe_df = self.fetch_data(pe_sym, date_start_str, date_end_str)
        
        if ce_df.empty or pe_df.empty: return balance, []

        # 5. Merge Everything
        spot_df = spot_df[['time', 'close']].rename(columns={'close': 'Spot'})
        fut_df = fut_df[['time', 'close', 'volume', 'oi']].rename(columns={'close': 'Fut', 'oi': 'OI_Fut', 'volume': 'Vol_Fut'})
        ce_df = ce_df[['time', 'close']].rename(columns={'close': 'CE'})
        pe_df = pe_df[['time', 'close']].rename(columns={'close': 'PE'})
        
        merged = pd.merge(spot_df, fut_df, on='time')
        merged = pd.merge(merged, ce_df, on='time', how='left').fillna(0)
        merged = pd.merge(merged, pe_df, on='time', how='left').fillna(0)

        # 6. Calculate Indicators
        # VWAP
        merged['VWAP'] = (merged['Vol_Fut'] * merged['Fut']).cumsum() / merged['Vol_Fut'].cumsum()
        # EMA
        merged['EMA5'] = merged['Spot'].ewm(span=5, adjust=False).mean()
        merged['EMA13'] = merged['Spot'].ewm(span=13, adjust=False).mean()
        # RSI (5-Min Logic on 1-Min Data)
        df_5m = merged.set_index('time').resample('5min').agg({'Spot': 'last'}).dropna()
        delta = df_5m['Spot'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain/loss
        df_5m['RSI'] = 100 - (100/(1+rs))
        
        merged = pd.merge_asof(merged, df_5m['RSI'], on='time', direction='backward')
        
        # 7. Run Intraday Logic
        return self.run_intraday_logic(merged, balance, atm_strike, ce_sym, pe_sym)

    def run_intraday_logic(self, df, start_balance, strike, ce_sym, pe_sym):
        balance = start_balance
        trades = []
        in_trade = False
        t_data = {}
        
        # Logs Buffer
        log_rows = []

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            t = row['time']
            rsi = row['RSI'] if not np.isnan(row['RSI']) else 50
            prev_rsi = prev['RSI'] if not np.isnan(prev['RSI']) else 50
            
            # --- LOGGING DATA PREP ---
            pcr_proxy = round(row['OI_Fut'] / row['Vol_Fut'], 2) if row['Vol_Fut'] > 0 else 0
            delta = self.calculate_greeks(row['Spot'], strike, 1) # Approx
            
            # 1. ENTRY SIGNALS (Reversal)
            if not in_trade:
                signal_ce = (prev_rsi < RSI_OVERSOLD) and (rsi >= RSI_OVERSOLD)
                signal_pe = (prev_rsi > RSI_OVERBOUGHT) and (rsi <= RSI_OVERBOUGHT)
                
                # Check Time (09:30 - 15:00)
                time_ok = 930 <= (t.hour*100 + t.minute) <= 1500

                if time_ok:
                    if signal_ce:
                        entry = row['CE']
                        if entry * LOT_SIZE <= balance:
                            in_trade = True
                            t_data = {
                                'entry_t': t, 'sym': ce_sym, 'type': 'CE', 'nifty_entry': row['Spot'],
                                'entry_p': entry, 'sl': entry - FIXED_SL, 'peak': entry,
                                'reason': 'RSI Oversold Reversal'
                            }
                            print(f"🟢 BUY CE {ce_sym} @ {entry}")
                    
                    elif signal_pe:
                        entry = row['PE']
                        if entry * LOT_SIZE <= balance:
                            in_trade = True
                            t_data = {
                                'entry_t': t, 'sym': pe_sym, 'type': 'PE', 'nifty_entry': row['Spot'],
                                'entry_p': entry, 'sl': entry - FIXED_SL, 'peak': entry,
                                'reason': 'RSI Overbought Reversal'
                            }
                            print(f"🔵 BUY PE {pe_sym} @ {entry}")

                # Log Movement (Scanning)
                status = "HOLD" if in_trade else "SCAN"
                reason = "In Trade" if in_trade else ("Waiting" if not (signal_ce or signal_pe) else "Signal Ignored")
                log_rows.append([
                    t, row['Spot'], row['VWAP'], row['EMA5'], row['EMA13'], 
                    strike, row['CE'], row['PE'], row['OI_Fut'], 0, pcr_proxy, delta, 
                    rsi, "Neutral", status, reason
                ])

            # 2. MANAGE TRADE (Trailing SL)
            elif in_trade:
                curr_price = row['CE'] if t_data['type'] == 'CE' else row['PE']
                
                # Update Peak
                if curr_price > t_data['peak']: t_data['peak'] = curr_price
                
                # TRAILING LOGIC
                profit = curr_price - t_data['entry_p']
                
                # Level 1: Move to Cost
                if profit >= TRAIL_ACTIVATE and t_data['sl'] < t_data['entry_p']:
                    t_data['sl'] = t_data['entry_p'] + 1 # Breakeven + 1
                
                # Level 2: Strict Trail
                if profit >= (TRAIL_ACTIVATE + 5):
                    new_sl = t_data['peak'] - TRAIL_GAP
                    if new_sl > t_data['sl']: t_data['sl'] = new_sl
                
                # EXIT CHECKS
                exit_res = None
                if curr_price <= t_data['sl']: exit_res = "SL Hit"
                elif t.hour == 15 and t.minute >= 15: exit_res = "EOD Exit"
                
                if exit_res:
                    pnl = (curr_price - t_data['entry_p']) * LOT_SIZE
                    balance += pnl
                    trades.append([
                        t_data['entry_t'], t, t_data['sym'], t_data['type'],
                        t_data['nifty_entry'], row['Spot'], t_data['entry_p'], curr_price,
                        t_data['peak'], t_data['sl'], t_data['sl'], # Trailing Px vs Final SL
                        pnl, balance, t_data['reason'], exit_res
                    ])
                    print(f"🔴 SELL {t_data['type']} @ {curr_price} | PnL: {pnl:.2f} ({exit_res})")
                    in_trade = False
                
                # Log Movement (In Trade)
                log_rows.append([
                    t, row['Spot'], row['VWAP'], row['EMA5'], row['EMA13'], 
                    strike, row['CE'], row['PE'], row['OI_Fut'], 0, pcr_proxy, delta, 
                    rsi, "In Trade", "HOLD", f"PnL: {profit*LOT_SIZE:.0f}"
                ])
                
        # Append logs to file
        pd.DataFrame(log_rows).to_csv(LOG_FILE, mode='a', header=False, index=False)
        pd.DataFrame(trades).to_csv(TRADE_FILE, mode='a', header=False, index=False)
        
        return balance, trades

    def run(self):
        print(f"🚀 Launching Time Machine for last {DAYS_TO_TEST} days...")
        current_balance = CAPITAL
        
        # Loop backwards from today
        for i in range(DAYS_TO_TEST, 0, -1):
            test_date = END_DATE - timedelta(days=i)
            # Skip weekends
            if test_date.weekday() > 4: continue
            
            print(f"📅 Processing {test_date.strftime('%Y-%m-%d')}...")
            current_balance, _ = self.process_daily_batch(test_date, current_balance)
            
        print("\n" + "="*60)
        print(f"FINAL BALANCE: {current_balance:.2f}")
        print(f"NET PROFIT   : {current_balance - CAPITAL:.2f}")
        print(f"👉 Detailed logs saved to {LOG_FILE} and {TRADE_FILE}")

if __name__ == "__main__":
    BacktesterV9().run()