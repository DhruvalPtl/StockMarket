# @title V66 - Institutional Sniper (With "Black Box" Data Recording)
from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import datetime
import time
import csv
import sys
import os
import pytz

# --- 🔐 CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- ⚠️ EXECUTION MODE ---
PAPER_MODE = True  # Set to False for Real Money
# -------------------------

# --- ⚙️ CONFIGURATION ---
CAPITAL = 10000.0
LOT_SIZE = 75
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"  
EXPIRY_TAG     = "23Dec25"

# Strategy Triggers
VOL_MULTIPLIER = 1.5          # Volume must be 1.5x Average
OI_DROP_THRESHOLD = -2.0      # OI must drop by 2% (Short Covering)

# Risk Management
SL_POINTS = 4.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0

# Files
TRADE_FILE = "V66_Trades.csv"
DATA_LOG_FILE = "V66_BlackBox_Log.csv" # <--- RECORDS EVERYTHING
IST = pytz.timezone('Asia/Kolkata')

# --- 📊 STATE ---
groww = None
position = None
active_symbol = None
entry_price = 0.0
sl_price = 0.0
highest_price = 0.0
trades_today = 0
MAX_TRADES = 3

# --- 📝 LOGGING ENGINE ---
def init_logs():
    # Initialize Data Log
    if not os.path.isfile(DATA_LOG_FILE):
        with open(DATA_LOG_FILE, "w", newline='') as f:
            csv.writer(f).writerow([
                "Timestamp", "Fut_Price", "Fut_VWAP", "Vol_Ratio", 
                "Opt_Symbol", "Opt_LTP", "Opt_OI_Chg", "Signal", "Status"
            ])

def log_heartbeat(fut_p, fut_vwap, vol_ratio, opt_sym, opt_ltp, oi_chg, signal):
    try:
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        status = "HOLDING" if position else "SCANNING"
        with open(DATA_LOG_FILE, "a", newline='') as f:
            csv.writer(f).writerow([
                ts, fut_p, round(fut_vwap, 2), round(vol_ratio, 2),
                opt_sym, opt_ltp, round(oi_chg, 2), signal, status
            ])
    except: pass

def log_trade(action, symbol, price, pnl, reason):
    if not os.path.isfile(TRADE_FILE):
        with open(TRADE_FILE, "w", newline='') as f:
            csv.writer(f).writerow(["Time", "Action", "Symbol", "Price", "PnL", "Reason", "Mode"])
    with open(TRADE_FILE, "a", newline='') as f:
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        mode = "PAPER" if PAPER_MODE else "REAL"
        csv.writer(f).writerow([ts, action, symbol, price, pnl, reason, mode])

def print_status(msg, end="\n"):
    ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
    sys.stdout.write(f"\r[{ts}] {msg}" + (" " * 10))
    if end == "\n": sys.stdout.write("\n")
    sys.stdout.flush()

# --- 🔌 CONNECT ---
def initialize():
    global groww
    try:
        print_status(f"🚀 INITIALIZING V66 SNIPER | Mode: {'PAPER' if PAPER_MODE else 'REAL'}")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print_status("✅ Connected.")
        init_logs()
    except Exception as e:
        print(f"\n❌ Auth Error: {e}")
        sys.exit()

# --- 📉 DATA ENGINE ---
def get_futures_trend():
    """Fetches Futures for VWAP and Volume Trend"""
    try:
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        
        # 1-min candles for precision
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if not resp or 'candles' not in resp: return 0, 0, 0

        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]

        # VWAP Math
        df['vp'] = ((df['high'] + df['low'] + df['close']) / 3) * df['volume']
        df['VWAP'] = df['vp'].cumsum() / df['volume'].cumsum()
        
        # Vol Ratio
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = df.iloc[-1]['volume'] / vol_avg if vol_avg > 0 else 0
        
        return df.iloc[-1]['close'], df.iloc[-1]['VWAP'], vol_ratio
    except: return 0, 0, 0

def get_option_data(fut_price):
    """Fetches Option Data (LTP & OI) using 5-min Candles (Verified Source)"""
    try:
        atm_strike = int(round(fut_price / 50) * 50)
        symbol = f"NSE-NIFTY-{EXPIRY_TAG}-{atm_strike}-CE"
        
        # Get 5-min candles for OI
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=15)
        
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        
        if not resp or 'candles' not in resp or len(resp['candles']) < 2: 
            return symbol, 0, 0
            
        curr = resp['candles'][-1]
        prev = resp['candles'][-2]
        
        ltp = curr[4]
        curr_oi = curr[6] if len(curr) > 6 else 0
        prev_oi = prev[6] if len(prev) > 6 else 0
        
        oi_chg = 0.0
        if prev_oi > 0:
            oi_chg = ((curr_oi - prev_oi) / prev_oi) * 100.0
            
        return symbol, ltp, oi_chg
    except: return "N/A", 0, 0

# --- 🔄 MAIN LOOP ---
def main():
    global position, active_symbol, entry_price, sl_price, highest_price, trades_today, CAPITAL
    initialize()
    
    while True:
        try:
            # 1. TIME CHECK
            now = datetime.datetime.now(IST)
            if now.time() < datetime.time(9, 15):
                print_status(f"Waiting... {now.strftime('%H:%M:%S')}", end="\r"); time.sleep(5); continue
            if now.time() > datetime.time(15, 25):
                print_status("Market Closed."); break
                
            # 2. GET DATA
            fut_p, fut_vwap, vol_ratio = get_futures_trend()
            if fut_p == 0: 
                print_status("Fetching Futures...", end="\r"); time.sleep(1); continue
                
            sym, opt_ltp, oi_chg = get_option_data(fut_p)
            
            # 3. LOGGING (Black Box)
            signal_log = "WAIT"
            if (fut_p > fut_vwap) and (vol_ratio > VOL_MULTIPLIER) and (oi_chg < OI_DROP_THRESHOLD):
                signal_log = "BUY_SIGNAL"
            
            log_heartbeat(fut_p, fut_vwap, vol_ratio, sym, opt_ltp, oi_chg, signal_log)
            
            # 4. DISPLAY
            disp = f"Fut: {fut_p:.1f} (VWAP {fut_vwap:.1f}) | Vol: {vol_ratio:.1f}x | CE OI Chg: {oi_chg:.2f}%"
            if position: disp += f" | PnL: {(opt_ltp - entry_price)*LOT_SIZE:.0f}"
            print_status(disp, end="\r")
            
            # 5. ENTRY LOGIC
            if position is None and trades_today < MAX_TRADES:
                if signal_log == "BUY_SIGNAL":
                    print(f"\n🚀 SIGNAL DETECTED! OI Dropped {oi_chg:.2f}%")
                    
                    # EXECUTE (Simulated or Real)
                    position = "CE"
                    active_symbol = sym
                    entry_price = opt_ltp
                    sl_price = entry_price - SL_POINTS
                    highest_price = entry_price
                    trades_today += 1
                    
                    msg = f"✅ BOUGHT {sym} @ {entry_price} (SL: {sl_price})"
                    print_status(msg)
                    log_trade("BUY", sym, entry_price, 0, "Signal")
            
            # 6. EXIT LOGIC
            elif position == "CE":
                curr_price = opt_ltp
                
                # Trail
                if curr_price > highest_price:
                    highest_price = curr_price
                    if (highest_price - entry_price) > TRAIL_TRIGGER:
                        new_sl = highest_price - TRAIL_GAP
                        if new_sl > sl_price: sl_price = new_sl
                
                # Stop
                if curr_price <= sl_price:
                    pnl = (sl_price - entry_price) * LOT_SIZE
                    CAPITAL += pnl
                    msg = f"🔴 SOLD {active_symbol} @ {sl_price} | PnL: {pnl:.2f}"
                    print_status(msg)
                    log_trade("SELL", active_symbol, sl_price, pnl, "SL/Trail")
                    position = None
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Stopped."); break
        except Exception as e:
            print(f"\n⚠️ Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()