# @title V62 - The "Short Covering Sniper" (VWAP + OI Logic)
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
EXPIRY_TAG = "23Dec25"       # <--- CONFIRM DATE
MAX_TRADES = 3               # Quality over Quantity (Research says 1-2 is best)

# STRATEGY SETTINGS (RESEARCH BASED)
VOL_MULTIPLIER = 1.5         # Volume must be 1.5x average
OI_CHANGE_THRESHOLD = 5.0    # 5% Drop in OI required for Short Covering signal

# RISK MANAGEMENT (SCALPING)
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
nifty_entry_val = 0.0 
sl_price = 0.0
highest_price = 0.0
trades_today = 0
daily_pnl = 0.0

# --- LOGGING ---
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
        print("✅ Auth Success (V62 Short Covering Sniper).")
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        sys.exit()

def construct_symbol(strike, type_):
    return f"NSE-NIFTY-{EXPIRY_TAG}-{strike}-{type_}"

# --- DATA ENGINE ---
def get_nifty_data():
    try:
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15)) # From Market Open for VWAP
        
        resp = groww.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY", 
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"), 
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if not resp or 'candles' not in resp: return None
        
        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        # VWAP CALCULATION
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['vp'] = df['tp'] * df['volume']
        df['total_vp'] = df['vp'].cumsum()
        df['total_vol'] = df['volume'].cumsum()
        df['VWAP'] = df['total_vp'] / df['total_vol']
        
        # 5-MIN RESAMPLE for Signal
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        
        df_5m = df.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
            'volume': 'sum', 'VWAP': 'last'
        }).dropna()
        
        if len(df_5m) < 20: return None
        
        # Volume Average
        df_5m['Vol_Avg'] = ta.sma(df_5m['volume'], length=15)
        
        return df_5m.iloc[-1] # Current Candle
    except: return None

def get_option_oi(strike, type_):
    # Fetches OI for a specific option to check Short Covering
    try:
        symbol = construct_symbol(strike, type_)
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=30) # Look back 30 mins
        
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_FNO, groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"), end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        if not resp or 'candles' not in resp: return 0, 0
        
        candles = resp['candles']
        if len(candles) < 2: return 0, 0
        
        curr_oi = candles[-1][6] if len(candles[-1]) > 6 else 0 # Assuming OI is col 6
        prev_oi = candles[-2][6] if len(candles[-2]) > 6 else 0
        
        if prev_oi == 0: return 0, 0
        
        # Calculate % Change
        oi_change = ((curr_oi - prev_oi) / prev_oi) * 100.0
        return curr_oi, oi_change
    except: return 0, 0

def get_affordable_symbol(nifty_ltp, type_):
    strike = int(round(nifty_ltp / 50) * 50)
    for i in range(3):
        symbol = construct_symbol(strike, type_)
        try:
            # Quick price check logic (simplified for speed)
            return symbol, 100.0, strike # Placeholder: In real logic use get_candle_price
        except: pass
        if type_ == "CE": strike += 50
        else: strike -= 50
    return None, 0, 0

def main():
    global position, active_symbol, entry_price, sl_price, highest_price, trades_today, CAPITAL
    
    initialize()
    print("🚀 V62 SNIPER: Scanning for Short Covering + VWAP Breakouts...")
    
    while True:
        try:
            now = datetime.datetime.now(IST)
            if now.time() < datetime.time(9, 30): # Research says skip first 15 mins
                print(f"Waiting for market settle (09:30)... {now.strftime('%H:%M:%S')}", end='\r')
                time.sleep(5); continue
                
            nifty = get_nifty_data()
            if nifty is None: time.sleep(2); continue
            
            price = nifty['close']
            vwap = nifty['VWAP']
            vol = nifty['volume']
            vol_avg = nifty['Vol_Avg']
            
            # ATM Strike for OI Check
            atm_strike = int(round(price / 50) * 50)
            
            # --- OI ANALYSIS (The "Secret Sauce") ---
            # Check ATM Call OI (Resistance) and ATM Put OI (Support)
            ce_oi, ce_oi_chg = get_option_oi(atm_strike, "CE")
            pe_oi, pe_oi_chg = get_option_oi(atm_strike, "PE")
            
            status = f"Nifty: {price:.1f} | VWAP: {vwap:.1f} | Vol: {vol/vol_avg:.1f}x"
            oi_status = f"CE OI: {ce_oi_chg:.1f}% | PE OI: {pe_oi_chg:.1f}%"
            print(f"\r{status} | {oi_status}      ", end='')
            
            # --- ENTRY LOGIC ---
            if position is None and trades_today < MAX_TRADES:
                
                # BUY CALL: Price > VWAP + Volume Spike + Call Shorts Exiting (OI Drop)
                if (price > vwap) and (vol > vol_avg * VOL_MULTIPLIER) and \
                   (ce_oi_chg < -OI_CHANGE_THRESHOLD): # Short Covering!
                    
                    symbol = construct_symbol(atm_strike, "CE")
                    # Real price fetch would go here
                    entry_price = 100.0 # Placeholder
                    
                    print(f"\n🚀 SHORT COVERING RALLY! Buying {symbol}")
                    position = "CE"; active_symbol = symbol
                    sl_price = entry_price - SL_POINTS
                    highest_price = entry_price
                    trades_today += 1
                
                # BUY PUT: Price < VWAP + Volume Spike + Put Shorts Exiting (Long Unwinding)
                elif (price < vwap) and (vol > vol_avg * VOL_MULTIPLIER) and \
                     (pe_oi_chg < -OI_CHANGE_THRESHOLD): # Long Unwinding!
                     
                    symbol = construct_symbol(atm_strike, "PE")
                    entry_price = 100.0 # Placeholder
                    
                    print(f"\n🚀 LONG UNWINDING! Buying {symbol}")
                    position = "PE"; active_symbol = symbol
                    sl_price = entry_price - SL_POINTS
                    highest_price = entry_price
                    trades_today += 1

            # --- EXIT LOGIC (Standard Scalp) ---
            elif position:
                # (Same Trailing Logic as before)
                # ...
                # If exit: position = None
                pass

            time.sleep(1)
            
        except KeyboardInterrupt: break
        except Exception as e: print(e); time.sleep(5)

if __name__ == "__main__":
    main()