# ================================================================
#  V58 - THE "PURE" 5-MINUTE BACKTESTER (Noise Filtered)
# ================================================================

from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import datetime
import csv
import sys

# --- CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ0NDI0MDQsImlhdCI6MTc2NjA0MjQwNCwibmJmIjoxNzY2MDQyNDA0LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhZTY1ODRjMC0yY2ViLTRiNzQtOGJhNi1hOWE3ZDA0NGI3OGRcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJiZjBmNjM2LTcxMWItNDhmYS04M2Y4LWFhMjYwYmFjNDA5OFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjE4NTpjZGM6Y2JhZDo1MDk1LDE3Mi42OS4xNzkuOTYsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ0NDI0MDQyODZ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.DcZojQEm-K8JH1XHXdz3cbI622Qz-APP3nJ3yf_DfAwdqhSqqdYEQYwLP36cUrsAs_RuWd1EZfI0ypTWW7Q9yA"
API_SECRET = "%HHhIe7l9bvm2r^vsS4c^^@VCQOfV^9l"

START_DATE = "2025-12-01"
END_DATE   = "2025-12-17"

CAPITAL = 10000.0
LOT_SIZE = 75
MAX_TRADES_PER_DAY = 5
MAX_OPT_PRICE = 200.0

# STRATEGY
EMA_FAST = 5
EMA_SLOW = 13
SL_POINTS = 15       
TRAIL_TRIGGER = 3    
TRAIL_GAP = 5         

# REALISM
SLIPPAGE = 1.0          
BROKERAGE = 50.0        

OUTPUT_FILE = "V58_Pure_5Min_Results2.csv"

# ================================================================

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"❌ Auth Failed: {e}")
        sys.exit()

def get_expiry_tag(groww, date_obj):
    try:
        resp = groww.get_expiries(exchange=groww.EXCHANGE_NSE, underlying_symbol="NIFTY", 
                                  year=date_obj.year, month=date_obj.month)
        if not resp or 'expiries' not in resp: return None
        target_date_str = date_obj.strftime("%Y-%m-%d")
        for exp in sorted(resp['expiries']):
            if exp >= target_date_str:
                d = datetime.datetime.strptime(exp, "%Y-%m-%d")
                return d.strftime("%d%b%y")
    except: pass
    return None

def construct_symbol(tag, strike, type_):
    return f"NSE-NIFTY-{tag}-{strike}-{type_}"

# --- DATA FETCHER ---
def fetch_data(groww, symbol, start_dt, end_dt, is_fno=False):
    segment = groww.SEGMENT_FNO if is_fno else groww.SEGMENT_CASH
    try:
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE, segment=segment, groww_symbol=symbol,
            start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval=groww.CANDLE_INTERVAL_MIN_1 # Fetch 1m raw to build 5m
        )
        if not resp or 'candles' not in resp or len(resp['candles']) == 0: return None
        df = pd.DataFrame(resp['candles'])
        if len(df.columns) >= 6:
            df = df.iloc[:, 0:6]
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if isinstance(df['timestamp'].iloc[0], str):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        return df
    except: return None

# --- SMART STRIKE SELECTOR ---
def get_entry_option(groww, tag, nifty_price, type_, entry_time, capital):
    strike = int(round(nifty_price / 50) * 50)
    for i in range(5):
        symbol = construct_symbol(tag, strike, type_)
        # Fetch just the entry candle (1 min is enough to get Open price)
        end_time = entry_time + datetime.timedelta(minutes=5) 
        df = fetch_data(groww, symbol, entry_time, end_time, True)
        if df is not None and not df.empty:
            entry_pr = df.iloc[0]['open']
            cost = entry_pr * LOT_SIZE
            if entry_pr > 5.0 and entry_pr < MAX_OPT_PRICE and cost <= capital:
                return symbol, entry_pr, strike
        if type_ == "CE": strike += 50
        else: strike -= 50
    return None, 0.0, 0

# --- MAIN ENGINE ---
def run_backtest():
    groww = auth()
    print("🚀 STARTING PURE 5-MINUTE BACKTEST...")
    
    with open(OUTPUT_FILE, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Time", "Type", "Strike", "Nifty_Ref", 
                         "Buy_Price", "Sell_Price", "Gross_PnL", "Net_PnL", "Balance", "Reason"])

    balance = CAPITAL
    current_date = datetime.datetime.strptime(START_DATE, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(END_DATE, "%Y-%m-%d")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n📅 Processing {date_str} | Bal: ₹{balance:.2f}...", end="")
        
        tag = get_expiry_tag(groww, current_date)
        if not tag:
            print(" (Skipped)")
            current_date += datetime.timedelta(days=1)
            continue
            
        s_time = datetime.datetime.strptime(f"{date_str} 09:15:00", "%Y-%m-%d %H:%M:%S")
        e_time = datetime.datetime.strptime(f"{date_str} 15:30:00", "%Y-%m-%d %H:%M:%S")
        
        nifty_1m = fetch_data(groww, "NSE-NIFTY", s_time, e_time)
        if nifty_1m is None:
            current_date += datetime.timedelta(days=1)
            continue
            
        # RESAMPLE TO 5-MIN (Signals)
        nifty_5m = nifty_1m.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
        }).dropna()
        
        nifty_5m['EMA_F'] = ta.ema(nifty_5m['close'], length=EMA_FAST)
        nifty_5m['EMA_S'] = ta.ema(nifty_5m['close'], length=EMA_SLOW)
        
        trades_today = 0
        last_trade_exit_time = s_time
        
        for i in range(2, len(nifty_5m)):
            if trades_today >= MAX_TRADES_PER_DAY: break
            
            curr = nifty_5m.iloc[i]
            prev = nifty_5m.iloc[i-1]
            signal_time = nifty_5m.index[i]
            
            if signal_time < last_trade_exit_time: continue
            if signal_time.time() > datetime.time(15, 00): break

            sig_type = None
            ema_f, ema_s = curr['EMA_F'], curr['EMA_S']
            prev_f, prev_s = prev['EMA_F'], prev['EMA_S']
            diff = ema_f - ema_s
            prev_diff = prev_f - prev_s
            
            # LOGIC
            if ema_f > ema_s and prev_f <= prev_s: sig_type = "CE"
            elif ema_f < ema_s and prev_f >= prev_s: sig_type = "PE"
            elif (ema_f > ema_s) and (diff > 2.0) and (diff > prev_diff) and \
                 (prev['close'] < prev['EMA_F']) and (curr['close'] > ema_f):
                sig_type = "CE"
            elif (ema_f < ema_s) and (diff < -2.0) and (diff < prev_diff) and \
                 (prev['close'] > prev['EMA_F']) and (curr['close'] < ema_f):
                sig_type = "PE"

            if sig_type:
                # ENTRY at 09:20 Signal -> 09:25 Candle Start (Realistic Delay)
                entry_time = signal_time + datetime.timedelta(minutes=5)
                
                if entry_time not in nifty_1m.index: continue
                nifty_entry_ref = nifty_1m.loc[entry_time]['open']
                
                sym, raw_entry_pr, strike = get_entry_option(groww, tag, nifty_entry_ref, sig_type, entry_time, balance)
                if not sym: continue
                
                buy_price = raw_entry_pr + SLIPPAGE
                
                # --- TRADE MANAGEMENT (PURE 5-MIN) ---
                # Fetch 1m data but resample to 5m for management
                opt_data_raw = fetch_data(groww, sym, entry_time, e_time, True)
                if opt_data_raw is None or opt_data_raw.empty: continue
                
                # THE FIX: Resample Option Data to 5-Min before checking stops
                opt_data_5m = opt_data_raw.resample('5min').agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                }).dropna()
                
                sl_price = buy_price - SL_POINTS
                highest_price = buy_price
                exit_price = 0.0
                reason = "EOD"
                
                for ts, candle in opt_data_5m.iterrows():
                    # 1. Update High (using 5-min High)
                    if candle['high'] > highest_price:
                        highest_price = candle['high']
                        if (highest_price - buy_price) > TRAIL_TRIGGER:
                            new_sl = highest_price - TRAIL_GAP
                            if new_sl > sl_price: sl_price = new_sl
                    
                    # 2. Check Stop (using 5-min Low)
                    if candle['low'] <= sl_price:
                        # Slippage Reality: If Low < SL, we effectively sold at SL
                        exit_price = sl_price
                        last_trade_exit_time = ts
                        reason = "SL/TRAIL"
                        break
                        
                if exit_price == 0.0:
                    exit_price = opt_data_5m.iloc[-1]['close']
                    last_trade_exit_time = opt_data_5m.index[-1]
                
                sell_price = exit_price - SLIPPAGE
                gross_pnl = (sell_price - buy_price) * LOT_SIZE
                net_pnl = gross_pnl - BROKERAGE
                balance += net_pnl
                trades_today += 1
                
                with open(OUTPUT_FILE, "a", newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        date_str, entry_time.strftime("%H:%M"), sig_type, sym,
                        round(nifty_entry_ref, 1),
                        round(buy_price, 2), round(sell_price, 2),
                        round(gross_pnl, 2), round(net_pnl, 2),
                        round(balance, 2), reason
                    ])
                    
        current_date += datetime.timedelta(days=1)

    print(f"\n✅ COMPLETE. Final Balance: ₹{balance:.2f}")
    print(f"📄 Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_backtest()