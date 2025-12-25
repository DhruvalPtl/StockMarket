# @title V55 - The "Rally Runner" (Balanced Risk & Trailing)
from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import time
import datetime
import csv
import sys
import os
import pytz

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQzNTIwMzYsImlhdCI6MTc2NTk1MjAzNiwibmJmIjoxNzY1OTUyMDM2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NzljMTAyNy03ZDQ1LTRlOWItYWM5ZS1iNDgzMWRiODQzZTFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjllODBhNjM2LTY4OGMtNDQ4OC1hMDhjLTU1NzQwMDQwNDMwZlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmM5ODU6OWEzNjo2ZTEyOjFjZWIsMTYyLjE1OC4yMzUuMjA0LDM1LjI0MS4yMy4xMjNcIixcInR3b0ZhRXhwaXJ5VHNcIjoyNTU0MzUyMDM2MzA0fSIsImlzcyI6ImFwZXgtYXV0aC1wcm9kLWFwcCJ9.vFYYnOrSLi-teVY6qhFF11SeSVZRIo-xBz_lVlOoTDujYw3ucWZSbOoP9sqFg11Oc8cCwWASqbg_R-9BfmPU0Q"
API_SECRET = "Gb!4#@-d4*XbNz)F!)Y0iW8122uJiaTn"

# --- CONFIGURATION ---
CAPITAL = 10000.0             
LOT_SIZE = 75
EXPIRY_TAG = "23Dec25"        # <--- CONFIRMED TAG

# STRATEGY (UPDATED FOR RALLY RUNNER)
EMA_FAST = 5
EMA_SLOW = 21
SL_POINTS = 5.0        # <--- BALANCED RISK (Give it room to survive noise)
TRAIL_TRIGGER = 5.0    # <--- RALLY MODE: Wait for ₹5 profit before trailing starts
TRAIL_GAP = 5.0        # <--- RALLY MODE: Allow 5 point pullback without selling
MAX_TRADES = 20        # <--- INCREASED: Don't stop at 5 if market is hot

# SYSTEM
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = "Live_System_Log_1min.txt"
TRACKER_FILE = "Live_Super_Tracker_1min.csv"
TRADE_BOOK = "Live_Trade_Book_1min.csv"

# STATE
groww = None
position = None
active_symbol = None
entry_price = 0.0     
nifty_entry_val = 0.0 
ema_fast_entry = 0.0
ema_slow_entry = 0.0
sl_price = 0.0
highest_price = 0.0
trades_today = 0
daily_pnl = 0.0

# --- LOGGING ENGINE ---
def log_system(message):
    timestamp = datetime.datetime.now(IST).strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    try:
        with open(LOG_FILE, "a") as f: f.write(formatted + "\n")
    except: pass

def log_super_tracker(status, nifty, ema_f, ema_s, diff, target_strike, symbol, 
                      opt_current, opt_entry, opt_exit, 
                      nifty_entry, nifty_exit, bal, d_pnl, reason):
    """
    Saves a detailed snapshot (One Row = One Second/Event)
    """
    file_exists = os.path.isfile(TRACKER_FILE)
    try:
        with open(TRACKER_FILE, "a", newline='') as f:
            writer = csv.writer(f)
            # Write Header if new file (Includes EMA_Diff)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Status", "Reason",
                    "Nifty_LTP", "EMA_5", "EMA_13", "EMA_Diff", 
                    "Target_Strike", "Active_Symbol", 
                    "Opt_Current", "Opt_Entry", "Opt_Exit", 
                    "Nifty_Entry", "Nifty_Exit", 
                    "Balance", "Daily_PnL"
                ])
            
            timestamp = datetime.datetime.now(IST).strftime("%H:%M:%S")
            
            def fmt(val): return round(val, 2) if isinstance(val, (int, float)) else 0.0

            writer.writerow([
                timestamp, status, reason,
                fmt(nifty), fmt(ema_f), fmt(ema_s), fmt(diff),
                target_strike, symbol,
                fmt(opt_current), fmt(opt_entry), fmt(opt_exit),
                fmt(nifty_entry), fmt(nifty_exit),
                fmt(bal), fmt(d_pnl)
            ])
    except: pass

def log_trade_book(entry_time, exit_time, type_, strike, buy_pr, sell_pr, 
                   nifty_in, nifty_out, ema_f_in, ema_s_in, pnl, bal, reason):
    """
    Saves the final result of a completed trade.
    """
    file_exists = os.path.isfile(TRADE_BOOK)
    try:
        with open(TRADE_BOOK, "a", newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "Entry Time", "Exit Time", "Type", "Strike", 
                                 "Opt Buy", "Opt Sell", "Nifty Entry", "Nifty Exit",
                                 "EMA5 Entry", "EMA13 Entry",
                                 "PnL", "Balance", "Reason"])
            writer.writerow([
                datetime.date.today(), entry_time, exit_time, type_, strike,
                round(buy_pr, 2), round(sell_pr, 2), 
                round(nifty_in, 2), round(nifty_out, 2),
                round(ema_f_in, 2), round(ema_s_in, 2),
                round(pnl, 2), round(bal, 2), reason
            ])
    except Exception as e:
        print(f"❌ CSV Error: {e}")

def initialize():
    global groww
    try:
        print("🔐 Authenticating...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ Auth Success (V55 Rally Runner).")
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        sys.exit()

def construct_symbol(strike, type_):
    return f"NSE-NIFTY-{EXPIRY_TAG}-{strike}-{type_}"

# --- CANDLE PRICE FETCHER ---
def get_candle_price(symbol):
    try:
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=5)
        
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_FNO,
            groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval=groww.CANDLE_INTERVAL_MIN_1 
        )
        if not resp or 'candles' not in resp or len(resp['candles']) == 0:
            return 0.0
        return float(resp['candles'][-1][4]) # Close Price
    except:
        return 0.0

def get_nifty_technical():
    try:
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(days=3) # Fetch less history for speed
        resp = groww.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY", 
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if not resp or 'candles' not in resp: return None, None
        
        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) == 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        # --- 1-MINUTE LOGIC (Turbo Mode) ---
        # We do NOT resample to 5min. We use the raw df.
        
        if isinstance(df['timestamp'].iloc[0], str): df['timestamp'] = pd.to_datetime(df['timestamp'])
        else: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        df.set_index('timestamp', inplace=True)
        df['close'] = df['close'].astype(float)
        
        # Calculate EMA directly on 1-minute candles
        df['EMA_Fast'] = ta.ema(df['close'], length=EMA_FAST)
        df['EMA_Slow'] = ta.ema(df['close'], length=EMA_SLOW)
        
        # Return the very last 1-minute candle
        return df.iloc[-1], df.iloc[-2]
    except: return None, None

# --- SMART STRIKE SELECTOR (Budget Protection) ---
def get_affordable_symbol(nifty_ltp, type_, capital):
    strike = int(round(nifty_ltp / 50) * 50)
    for i in range(5):
        symbol = construct_symbol(strike, type_)
        price = get_candle_price(symbol)
        cost = price * LOT_SIZE
        if price > 5.0 and cost <= capital:
            return symbol, price, strike
        
        # Move OTM if too expensive
        if type_ == "CE": strike += 50 
        else: strike -= 50
            
    return None, 0.0, 0

def main():
    global position, active_symbol, entry_price, nifty_entry_val, ema_fast_entry, ema_slow_entry
    global sl_price, highest_price, trades_today, CAPITAL, daily_pnl
    
    initialize()
    entry_time_str = ""
    
    print(f"📊 Tracking every tick to: {TRACKER_FILE}")
    
    while True:
        try:
            now = datetime.datetime.now(IST)
            
            # --- TIME CHECK ---
            if now.time() < datetime.time(9, 15):
                print(f"Waiting... {now.strftime('%H:%M:%S')}", end='\r')
                time.sleep(5)
                continue
            
            if now.time() > datetime.time(15, 25):
                log_system("⏰ Market Closing.")
                break

            # --- DATA FETCH ---
            curr, prev = get_nifty_technical()
            if curr is None:
                print("Fetching Nifty...", end='\r')
                time.sleep(2)
                continue

            ema_f, ema_s = curr['EMA_Fast'], curr['EMA_Slow']
            prev_f, prev_s = prev['EMA_Fast'], prev['EMA_Slow']
            nifty_ltp = curr['close']
            current_diff = ema_f - ema_s

            # --- PREPARE DATA FOR LOGGING ---
            target_strike = int(round(nifty_ltp / 50) * 50)
            
            watch_type = "CE" if ema_f > ema_s else "PE"
            watch_symbol = construct_symbol(target_strike, watch_type)
            live_opt_price = get_candle_price(watch_symbol)
            
            status_display = "SCANNING"
            reason_display = "WAIT"
            symbol_display = watch_symbol
            
            if position:
                live_opt_price = get_candle_price(active_symbol)
                status_display = "HOLDING"
                reason_display = f"{position}"
                symbol_display = active_symbol
                
                pnl = (live_opt_price - entry_price) * LOT_SIZE
                sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] Nifty: {nifty_ltp:.1f} | {active_symbol}: {live_opt_price} | PnL: {pnl:.0f}   ")
            else:
                reason_display = f"WATCH_{watch_type}"
                sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] Nifty: {nifty_ltp:.1f} | Watch: {watch_type} {target_strike} @ {live_opt_price} | Diff: {current_diff:.2f}   ")

            sys.stdout.flush()

            # ** 📝 LOG SUPER TRACKER **
            log_super_tracker(
                status_display, nifty_ltp, ema_f, ema_s, current_diff, target_strike, symbol_display,
                live_opt_price, entry_price, 0.0, 
                nifty_entry_val, 0.0, 
                CAPITAL, daily_pnl, reason_display
            )

            # --- ENTRY LOGIC (UPDATED: DIP BUYER + CROSSOVER) ---
            if position is None and trades_today < MAX_TRADES:
                sig_type = None
                
                # 1. CLASSIC CROSSOVER
                if ema_f > ema_s and prev_f <= prev_s: sig_type = "CE"
                elif ema_f < ema_s and prev_f >= prev_s: sig_type = "PE"
                
                # 2. RALLY CATCHER (Dip Buy)
                elif (ema_f > ema_s) and (prev['close'] < prev['EMA_Fast']) and (curr['close'] > ema_f):
                    sig_type = "CE"
                elif (ema_f < ema_s) and (prev['close'] > prev['EMA_Fast']) and (curr['close'] < ema_f):
                    sig_type = "PE"
                
                if sig_type:
                    # SMART SHOPPER
                    symbol, price, strike = get_affordable_symbol(nifty_ltp, sig_type, CAPITAL)
                    
                    if symbol and price > 0:
                        print("")
                        log_system(f"🚀 TRADE EXECUTED: {sig_type} | Nifty: {nifty_ltp}")
                        position = sig_type
                        active_symbol = symbol
                        entry_price = price
                        nifty_entry_val = nifty_ltp
                        ema_fast_entry = ema_f
                        ema_slow_entry = ema_s
                        
                        sl_price = entry_price - SL_POINTS
                        highest_price = price
                        entry_time_str = now.strftime("%H:%M:%S")
                        trades_today += 1
                        
                        log_system(f"✅ BOUGHT {symbol} @ {price} | SL: {sl_price}")

            # --- EXIT LOGIC (UPDATED TRAIL) ---
            elif position:
                if live_opt_price <= 0: continue
                
                # Trail
                if live_opt_price > highest_price:
                    highest_price = live_opt_price
                    # Only Trail if profit > TRIGGER
                    if (highest_price - entry_price) > TRAIL_TRIGGER:
                        new_sl = highest_price - TRAIL_GAP
                        if new_sl > sl_price: sl_price = new_sl
                
                is_stop = live_opt_price <= sl_price
                is_rev = (position == "CE" and ema_f < ema_s) or (position == "PE" and ema_f > ema_s)
                
                if is_stop or is_rev:
                    print("")
                    reason = "STOP/TRAIL" if is_stop else "REVERSAL"
                    exit_price = sl_price if is_stop else live_opt_price
                    
                    trade_pnl = (exit_price - entry_price) * LOT_SIZE
                    CAPITAL += trade_pnl
                    daily_pnl += trade_pnl
                    
                    log_system(f"🔴 SOLD @ {exit_price} | PnL: {trade_pnl:.2f} ({reason})")
                    
                    log_trade_book(
                        entry_time_str, now.strftime("%H:%M:%S"), position, active_symbol, 
                        entry_price, exit_price, 
                        nifty_entry_val, nifty_ltp, 
                        ema_fast_entry, ema_slow_entry,
                        trade_pnl, CAPITAL, reason
                    )
                    
                    log_super_tracker(
                        "SOLD", nifty_ltp, ema_f, ema_s, current_diff, target_strike, active_symbol,
                        live_opt_price, entry_price, exit_price, 
                        nifty_entry_val, nifty_ltp, 
                        CAPITAL, daily_pnl, reason
                    )
                    
                    position = None
                    active_symbol = None

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nBot Stopped.")
            break
        except Exception as e:
            print(f"\n⚠️ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()