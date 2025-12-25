import pandas as pd
import datetime
import sys
from growwapi import GrowwAPI

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
# REPLACE THESE WITH YOUR ACTUAL KEYS
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# SYMBOLS & DATES (Make sure these are correct for the dates you test!)
FUT_SYMBOL     = "NSE-NIFTY-30Dec25-FUT" 
# NOTE: Ensure this expiry existed during your test dates (Dec 15-19)
OPT_EXPIRY_STR = "23Dec25"  

# STRATEGY SETTINGS
CAPITAL       = 10000.0
LOT_SIZE      = 75
SL_POINTS     = 8.0   # Hard Stop Loss
TRAIL_TRIGGER = 10.0  # Profit needed to activate trailing
TRAIL_GAP     = 5.0   # Distance to trail behind
OI_THRESHOLD  = -5000 # Minimum drop in OI to confirm short covering

class BacktesterV92:
    def __init__(self):
        print("--- [V92] INITIALIZING ---")
        try:
            # 1. Auto-Login (No hardcoded tokens)
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            print("✅ Login Successful.")
        except Exception as e:
            print(f"❌ Critical Auth Error: {e}")
            sys.exit()
            
        self.option_db = {} # Database to store option data

    def fetch_data(self, symbol):
        """Robust data fetcher with error handling"""
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=5) # Last 5 days
        try:
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", symbol,
                start.strftime("%Y-%m-%d %H:%M:%S"), 
                end.strftime("%Y-%m-%d %H:%M:%S"), 
                "5minute" # Using 5min for stability
            )
            if not resp or 'candles' not in resp or len(resp['candles']) == 0:
                return None
                
            df = pd.DataFrame(resp['candles'], columns=['timestamp','open','high','low','close','volume','oi'])
            # Fix timestamps (remove 'T')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Clean Data (Forward Fill)
            df['close'] = df['close'].ffill()
            df['oi'] = df['oi'].ffill().fillna(0)
            return df
        except Exception as e:
            print(f"⚠️ Error fetching {symbol}: {e}")
            return None

    def run(self):
        print(f"📥 Fetching Futures Data: {FUT_SYMBOL}...")
        fut_df = self.fetch_data(FUT_SYMBOL)
        if fut_df is None:
            print("❌ Error: No Futures Data. Check Symbol.")
            return

        # Calculate Indicators
        fut_df['vwap'] = (fut_df['close'] * fut_df['volume']).cumsum() / fut_df['volume'].cumsum()
        fut_df['oi_chg'] = fut_df['oi'].diff()
        
        balance = CAPITAL
        trades = []
        in_trade = False
        trade_data = {}

        print("🚀 Starting Simulation...")
        print("-" * 80)

        for i in range(1, len(fut_df)):
            row = fut_df.iloc[i]
            prev_row = fut_df.iloc[i-1]
            
            curr_time = row['timestamp']
            price = row['close']
            vwap = row['vwap']
            oi_chg = row['oi_chg']

            # ==============================
            # 1. ENTRY LOGIC
            # ==============================
            if not in_trade:
                # STRATEGY: Price > VWAP + OI Dropping (Short Covering)
                # Only trade between 09:30 and 14:30
                time_ok = datetime.time(9, 30) <= curr_time.time() <= datetime.time(14, 30)
                
                if time_ok and price > vwap and oi_chg < OI_THRESHOLD:
                    # Select Strike
                    atm = round(price / 50) * 50
                    strike_sym = f"NSE-NIFTY-{OPT_EXPIRY_STR}-{atm}-CE"
                    
                    # Fetch Option Data JUST-IN-TIME (Efficient)
                    if strike_sym not in self.option_db:
                        print(f"   🔎 Fetching Option: {strike_sym}...")
                        self.option_db[strike_sym] = self.fetch_data(strike_sym)
                    
                    opt_df = self.option_db.get(strike_sym)
                    
                    if opt_df is not None:
                        # Find the option candle matching current time
                        # "asof" finds the nearest candle if exact match missing
                        try:
                            opt_candle = opt_df.iloc[opt_df.index.get_indexer([curr_time], method='nearest')[0]]
                            opt_price = opt_candle['close']
                            
                            # Budget Check
                            if opt_price * LOT_SIZE <= balance:
                                in_trade = True
                                trade_data = {
                                    'entry_time': curr_time,
                                    'symbol': strike_sym,
                                    'type': 'BUY',
                                    'entry_price': opt_price,
                                    'sl': opt_price - SL_POINTS,
                                    'peak': opt_price
                                }
                                print(f"🟢 BUY {strike_sym} @ {opt_price} | Fut: {price}")
                        except:
                            continue

            # ==============================
            # 2. EXIT & MANAGEMENT
            # ==============================
            elif in_trade:
                # Update Option Price
                opt_df = self.option_db[trade_data['symbol']]
                try:
                    # Find current price of the option we own
                    idx = opt_df['timestamp'].searchsorted(curr_time)
                    if idx >= len(opt_df): idx = len(opt_df) - 1
                    curr_opt_price = opt_df.iloc[idx]['close']
                except:
                    continue

                # Trailing SL Logic
                trade_data['peak'] = max(trade_data['peak'], curr_opt_price)
                if (curr_opt_price - trade_data['entry_price']) > TRAIL_TRIGGER:
                    new_sl = trade_data['peak'] - TRAIL_GAP
                    trade_data['sl'] = max(trade_data['sl'], new_sl)

                # Check Exit
                reason = None
                if curr_opt_price <= trade_data['sl']:
                    reason = "SL Hit"
                elif curr_time.time() >= datetime.time(15, 15):
                    reason = "EOD Exit"

                if reason:
                    pnl = (curr_opt_price - trade_data['entry_price']) * LOT_SIZE
                    balance += pnl
                    trades.append({
                        'Time': curr_time,
                        'Symbol': trade_data['symbol'],
                        'Entry': trade_data['entry_price'],
                        'Exit': curr_opt_price,
                        'PnL': pnl,
                        'Reason': reason
                    })
                    print(f"🔴 SELL {trade_data['symbol']} @ {curr_opt_price} | PnL: {pnl:.2f} ({reason})")
                    in_trade = False

        # ==============================
        # 📊 FINAL REPORT
        # ==============================
        print("\n" + "="*80)
        print("V92 TRADE BOOK")
        print("="*80)
        df_res = pd.DataFrame(trades)
        if not df_res.empty:
            print(df_res[['Time', 'Symbol', 'Entry', 'Exit', 'PnL', 'Reason']].to_string(index=False))
            print("-" * 80)
            print(f"START CAPITAL: {CAPITAL}")
            print(f"FINAL BALANCE: {balance:.2f}")
            print(f"NET PnL:       {balance - CAPITAL:.2f}")
        else:
            print("No trades executed (Criteria too strict or Data missing).")

if __name__ == "__main__":
    BacktesterV92().run()