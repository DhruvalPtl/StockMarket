# @title V65 - The "Short Covering" Sniper (Live Execution Engine)
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
PAPER_MODE = True  # <--- SET TO FALSE TO TRADE REAL MONEY
# -------------------------

# --- ⚙️ CONFIGURATION ---
CAPITAL = 10000.0
LOT_SIZE = 75

# Symbols (Verified)
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"  
EXPIRY_TAG     = "23Dec25"                

# Strategy Triggers
VOL_MULTIPLIER = 1.5          # Volume must be 1.5x Average
OI_DROP_THRESHOLD = -2.0      # OI must drop by 2% (Short Covering)

# Scalper Risk Management
SL_POINTS = 4.0               # Hard Stop Loss
TRAIL_TRIGGER = 3.0           # Profit needed to start trailing
TRAIL_GAP = 2.0               # Trailing distance

# Logging
LOG_FILE = "V65_Live_Trades.csv"
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

def print_status(msg, end="\n"):
    ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
    sys.stdout.write(f"\r[{ts}] {msg}" + (" " * 10))
    if end == "\n": sys.stdout.write("\n")
    sys.stdout.flush()

def log_trade(action, symbol, price, pnl, reason):
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, "w", newline='') as f:
            csv.writer(f).writerow(["Time", "Action", "Symbol", "Price", "PnL", "Reason", "Mode"])
    with open(LOG_FILE, "a", newline='') as f:
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        mode = "PAPER" if PAPER_MODE else "REAL"
        csv.writer(f).writerow([ts, action, symbol, price, pnl, reason, mode])

# --- 🔌 CONNECT ---
def initialize():
    global groww
    try:
        print_status(f"🚀 INITIALIZING V65 SNIPER | Mode: {'PAPER' if PAPER_MODE else 'REAL MONEY'}")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print_status("✅ Connected to Groww API.")
    except Exception as e:
        print(f"\n❌ Auth Error: {e}")
        sys.exit()

# --- 📉 DATA ENGINE ---
def get_futures_trend():
    """Returns: Price, VWAP, Vol_Ratio"""
    try:
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        
        # 1-min candles for precise VWAP
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

        # VWAP Calculation
        df['vp'] = ((df['high'] + df['low'] + df['close']) / 3) * df['volume']
        df['VWAP'] = df['vp'].cumsum() / df['volume'].cumsum()
        
        # Relative Volume
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = df.iloc[-1]['volume'] / vol_avg if vol_avg > 0 else 0
        
        return df.iloc[-1]['close'], df.iloc[-1]['VWAP'], vol_ratio
    except: return 0, 0, 0

def get_option_oi_data(fut_price):
    """Returns: Symbol, LTP, OI Change %"""
    try:
        # 1. Find ATM Strike
        atm_strike = int(round(fut_price / 50) * 50)
        symbol = f"NSE-NIFTY-{EXPIRY_TAG}-{atm_strike}-CE" # Checking Call Side
        
        # 2. Get 5-min candles (Verified Source for OI)
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=15)
        
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        
        if not resp or 'candles' not in resp or len(resp['candles']) < 2: 
            return None, 0, 0
            
        curr = resp['candles'][-1]
        prev = resp['candles'][-2]
        
        ltp = curr[4]
        curr_oi = curr[6] if len(curr) > 6 else 0
        prev_oi = prev[6] if len(prev) > 6 else 0
        
        oi_chg = 0.0
        if prev_oi > 0:
            oi_chg = ((curr_oi - prev_oi) / prev_oi) * 100.0
            
        return symbol, ltp, oi_chg
    except: return None, 0, 0

# --- 🔫 EXECUTION ENGINE ---
def place_order(symbol, buy_sell, quantity):
    if PAPER_MODE:
        return True # Simulate success
    
    try:
        # REAL ORDER PLACEMENT
        # order = groww.place_order(
        #     exchange=groww.EXCHANGE_NSE,
        #     symbol=symbol,
        #     transaction_type=buy_sell, # "BUY" or "SELL"
        #     quantity=quantity,
        #     price=0, # Market Order
        #     product=groww.PRODUCT_MIS,
        #     order_type=groww.ORDER_TYPE_MARKET
        # )
        # return 'id' in order
        pass # Uncomment above for real execution
    except Exception as e:
        print_status(f"❌ Order Failed: {e}")
        return False

# --- 🔄 MAIN LOOP ---
def main():
    global position, active_symbol, entry_price, sl_price, highest_price, trades_today, CAPITAL
    initialize()
    
    while True:
        try:
            # 1. MARKET TIME CHECK
            now = datetime.datetime.now(IST)
            if now.time() < datetime.time(9, 15):
                print_status(f"Waiting... {now.strftime('%H:%M:%S')}", end="\r")
                time.sleep(5); continue
            if now.time() > datetime.time(15, 25):
                print_status("Market Closed."); break
                
            # 2. ANALYZE FUTURES (The Trend)
            fut_p, fut_vwap, vol_ratio = get_futures_trend()
            if fut_p == 0: 
                print_status("Fetching Futures...", end="\r"); time.sleep(1); continue
                
            # 3. ANALYZE OPTIONS (The Trigger)
            # We focus on Calls (CE) for Short Covering Rallies
            sym, opt_ltp, oi_chg = get_option_oi_data(fut_p)
            
            # Status Display
            status = f"Fut: {fut_p:.1f} (VWAP {fut_vwap:.1f}) | Vol: {vol_ratio:.1f}x"
            oi_status = f" | CE OI Chg: {oi_chg:.2f}%"
            pnl_status = f" | PnL: {(opt_ltp - entry_price)*LOT_SIZE:.0f}" if position else ""
            print_status(status + oi_status + pnl_status, end="\r")
            
            # --- ENTRY LOGIC ---
            if position is None and trades_today < MAX_TRADES:
                # Rule: Trend Up (Price > VWAP) + Volume Spike + Short Covering (OI Drop)
                if (fut_p > fut_vwap) and (vol_ratio > VOL_MULTIPLIER) and (oi_chg < OI_DROP_THRESHOLD):
                    
                    print(f"\n🚀 SIGNAL: Short Covering Detected! ({oi_chg:.2f}% OI Drop)")
                    
                    # EXECUTE BUY
                    if PAPER_MODE or place_order(sym, "BUY", LOT_SIZE):
                        position = "CE"
                        active_symbol = sym
                        entry_price = opt_ltp
                        sl_price = entry_price - SL_POINTS
                        highest_price = entry_price
                        trades_today += 1
                        
                        msg = f"✅ BOUGHT {sym} @ {entry_price} (SL: {sl_price})"
                        print_status(msg)
                        log_trade("BUY", sym, entry_price, 0, "Signal")
            
            # --- EXIT LOGIC (SCALPER) ---
            elif position == "CE":
                # Update Price (Simulated or Real fetch needed here ideally, using last fetch)
                curr_price = opt_ltp 
                
                # 1. Trail Stop
                if curr_price > highest_price:
                    highest_price = curr_price
                    if (highest_price - entry_price) > TRAIL_TRIGGER:
                        new_sl = highest_price - TRAIL_GAP
                        if new_sl > sl_price: sl_price = new_sl
                
                # 2. Check Stop
                if curr_price <= sl_price:
                    # EXECUTE SELL
                    if PAPER_MODE or place_order(active_symbol, "SELL", LOT_SIZE):
                        pnl = (sl_price - entry_price) * LOT_SIZE
                        CAPITAL += pnl
                        
                        msg = f"🔴 SOLD {active_symbol} @ {sl_price} | PnL: {pnl:.2f}"
                        print_status(msg)
                        log_trade("SELL", active_symbol, sl_price, pnl, "SL/Trail")
                        position = None
            
            time.sleep(1) # Heartbeat
            
        except KeyboardInterrupt:
            print("\n🛑 Bot Stopped."); break
        except Exception as e:
            print(f"\n⚠️ Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()