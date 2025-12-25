# @title V63 - The "Futures-Powered" Short Covering Sniper
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
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"

# --- CONFIGURATION ---
CAPITAL = 10000.0             
LOT_SIZE = 75
EXPIRY_TAG = "23Dec25"        # <--- For Options (e.g., Weekly)
FUTURES_SYMBOL = "NSE-NIFTY-26Dec25-FUT" # <--- NEW: Enter Monthly Futures Symbol for VWAP

MAX_TRADES = 3                # Limit to best 3 setups
VOL_MULTIPLIER = 1.5          # Volume must be 1.5x Average
OI_CHANGE_THRESHOLD = 5.0     # 5% Drop in OI required

# RISK MANAGEMENT
SL_POINTS = 10.0             
TRAIL_TRIGGER = 10.0         
TRAIL_GAP = 5.0              

# SYSTEM
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = "Live_System_Log.txt"
TRACKER_FILE = "Live_Super_Tracker.csv"
TRADE_BOOK = "Live_Trade_Book.csv"

# STATE
groww = None
position = None
active_symbol = None
entry_price = 0.0     
sl_price = 0.0
highest_price = 0.0
trades_today = 0
daily_pnl = 0.0

def log_system(message):
    timestamp = datetime.datetime.now(IST).strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    try:
        with open(LOG_FILE, "a") as f: f.write(f"[{timestamp}] {message}\n")
    except: pass

def log_trade(type_, symbol, buy, sell, pnl, reason):
    try:
        with open(TRADE_BOOK, "a", newline='') as f:
            csv.writer(f).writerow([datetime.datetime.now(IST), type_, symbol, buy, sell, pnl, reason])
    except: pass

def initialize():
    global groww
    try:
        print("🔐 Authenticating...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print("✅ Auth Success (V63 Futures Logic).")
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        sys.exit()

def construct_option_symbol(strike, type_):
    return f"NSE-NIFTY-{EXPIRY_TAG}-{strike}-{type_}"

# --- DATA ENGINE (HYBRID) ---
def get_futures_data():
    """
    Fetches Nifty Futures Data to calculate VWAP and Volume.
    """
    try:
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        
        # Fetch Futures Candles
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL, 
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"), 
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if not resp or 'candles' not in resp: return None
        
        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        # VWAP CALCULATION (On Futures)
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['vp'] = df['tp'] * df['volume']
        df['total_vp'] = df['vp'].cumsum()
        df['total_vol'] = df['volume'].cumsum()
        df['VWAP'] = df['total_vp'] / df['total_vol']
        
        # 5-MIN RESAMPLE
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        
        df_5m = df.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
            'volume': 'sum', 'VWAP': 'last'
        }).dropna()
        
        if len(df_5m) < 20: return None
        
        # Calculate Average Volume
        df_5m['Vol_Avg'] = ta.sma(df_5m['volume'], length=15)
        
        return df_5m.iloc[-1] # Return latest candle
    except: return None

def get_option_oi(strike, type_):
    """
    Fetches Option OI to detect Short Covering.
    """
    try:
        symbol = construct_option_symbol(strike, type_)
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=30)
        
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_FNO, groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"), end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        if not resp or 'candles' not in resp: return 0, 0
        
        candles = resp['candles']
        if len(candles) < 2: return 0, 0
        
        # OI is usually the last column (index 6 or 5)
        curr_oi = candles[-1][6] if len(candles[-1]) > 6 else 0
        prev_oi = candles[-2][6] if len(candles[-2]) > 6 else 0
        
        if prev_oi == 0: return 0, 0
        
        # % Change in OI
        oi_change = ((curr_oi - prev_oi) / prev_oi) * 100.0
        return curr_oi, oi_change
    except: return 0, 0

def get_candle_price(symbol):
    try:
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=5)
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_FNO, groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"), end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval=groww.CANDLE_INTERVAL_MIN_1 
        )
        if not resp or 'candles' not in resp: return 0.0
        return float(resp['candles'][-1][4])
    except: return 0.0

def get_affordable_symbol(nifty_ltp, type_, capital):
    strike = int(round(nifty_ltp / 50) * 50)
    for i in range(3):
        symbol = construct_option_symbol(strike, type_)
        price = get_candle_price(symbol)
        cost = price * LOT_SIZE
        if price > 5.0 and cost <= capital: return symbol, price, strike
        if type_ == "CE": strike += 50 
        else: strike -= 50
    return None, 0.0, 0

def main():
    global position, active_symbol, entry_price, sl_price, highest_price, trades_today, CAPITAL
    
    initialize()
    print(f"🚀 V63 HYBRID: Futures ({FUTURES_SYMBOL}) for Trend | Options for Trade")
    
    while True:
        try:
            now = datetime.datetime.now(IST)
            if now.time() < datetime.time(9, 30):
                print(f"Waiting for market settle... {now.strftime('%H:%M:%S')}", end='\r')
                time.sleep(5); continue
            if now.time() > datetime.time(15, 25):
                log_system("⏰ Market Closing."); break
                
            # 1. Fetch Futures Data (Trend & VWAP)
            fut_data = get_futures_data()
            if fut_data is None: 
                print("Fetching Futures...", end='\r'); time.sleep(2); continue
            
            fut_price = fut_data['close']
            vwap = fut_data['VWAP']
            vol = fut_data['volume']
            vol_avg = fut_data['Vol_Avg']
            
            # 2. Use Futures Price to find ATM Strike
            atm_strike = int(round(fut_price / 50) * 50)
            
            # 3. Check Option OI (Trigger)
            ce_oi, ce_oi_chg = get_option_oi(atm_strike, "CE")
            pe_oi, pe_oi_chg = get_option_oi(atm_strike, "PE")
            
            status = f"Fut: {fut_price:.1f} | VWAP: {vwap:.1f} | Vol: {vol/vol_avg:.1f}x"
            oi_status = f"CE OI Chg: {ce_oi_chg:.1f}% | PE OI Chg: {pe_oi_chg:.1f}%"
            
            if position:
                curr_pr = get_candle_price(active_symbol)
                pnl = (curr_pr - entry_price) * LOT_SIZE
                sys.stdout.write(f"\r{status} | HOLD {active_symbol} | PnL: {pnl:.0f}   ")
            else:
                sys.stdout.write(f"\r{status} | {oi_status}   ")
            sys.stdout.flush()
            
            # --- ENTRY LOGIC ---
            if position is None and trades_today < MAX_TRADES:
                sig_type = None
                
                # BUY CALL: Futures > VWAP + Volume Spike + Call OI Drop (Short Covering)
                if (fut_price > vwap) and (vol > vol_avg * VOL_MULTIPLIER) and (ce_oi_chg < -OI_CHANGE_THRESHOLD):
                    sig_type = "CE"
                    print(f"\n🚀 SHORT COVERING DETECTED! (Call OI Dropped {ce_oi_chg:.1f}%)")
                    
                # BUY PUT: Futures < VWAP + Volume Spike + Put OI Drop (Long Unwinding)
                elif (fut_price < vwap) and (vol > vol_avg * VOL_MULTIPLIER) and (pe_oi_chg < -OI_CHANGE_THRESHOLD):
                    sig_type = "PE"
                    print(f"\n🚀 LONG UNWINDING DETECTED! (Put OI Dropped {pe_oi_chg:.1f}%)")
                
                if sig_type:
                    symbol, price, strike = get_affordable_symbol(fut_price, sig_type, CAPITAL)
                    if symbol:
                        log_system(f"✅ BOUGHT {symbol} @ {price} | Fut: {fut_price}")
                        position = sig_type; active_symbol = symbol; entry_price = price
                        sl_price = entry_price - SL_POINTS; highest_price = price
                        trades_today += 1
            
            # --- EXIT LOGIC ---
            elif position:
                curr_pr = get_candle_price(active_symbol)
                if curr_pr > 0:
                    # Trail
                    if curr_pr > highest_price:
                        highest_price = curr_pr
                        if (highest_price - entry_price) > TRAIL_TRIGGER:
                            new_sl = highest_price - TRAIL_GAP
                            if new_sl > sl_price: sl_price = new_sl
                    
                    if curr_pr <= sl_price:
                        pnl = (sl_price - entry_price) * LOT_SIZE
                        log_system(f"🔴 SOLD {active_symbol} @ {sl_price} | PnL: {pnl:.0f}")
                        log_trade(position, active_symbol, entry_price, sl_price, pnl, "SL/TRAIL")
                        position = None

            time.sleep(1)
            
        except KeyboardInterrupt: break
        except Exception as e: print(e); time.sleep(5)

if __name__ == "__main__":
    main()