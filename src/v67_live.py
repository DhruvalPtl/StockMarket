# @title V67 - "Double-Barreled" Sniper (Revised with Option Chain Data)
from growwapi import GrowwAPI
import pandas as pd
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
PAPER_MODE = True
# -------------------------

# --- ⚙️ CONFIGURATION ---
CAPITAL = 10000.0
LOT_SIZE = 75
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" # Still need this for VWAP Volume
EXPIRY_DATE    = "2025-12-23"             # For Option Chain Fetch

# Strategy Triggers
VOL_MULTIPLIER = 1.5
OI_DROP_THRESHOLD = -2.0  # Panic Signal

# Risk Management
SL_POINTS = 4.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0

# Logging
LOG_FILE = "V67_RealData_Log.csv"
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

def log_heartbeat(trend, spot_p, fut_vwap, vol_ratio, strike, o_type, o_ltp, o_oi, o_oi_chg, signal):
    try:
        if not os.path.isfile(LOG_FILE):
             with open(LOG_FILE, "w", newline='') as f:
                csv.writer(f).writerow(["Timestamp", "Trend", "Spot_Price", "Fut_VWAP", "Vol_Ratio", "Strike", "Type", "LTP", "OI", "OI_Chg", "Signal"])
        
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        with open(LOG_FILE, "a", newline='') as f:
            csv.writer(f).writerow([
                ts, trend, spot_p, round(fut_vwap, 2), round(vol_ratio, 2),
                strike, o_type, o_ltp, o_oi, round(o_oi_chg, 2), signal
            ])
    except: pass

def initialize():
    global groww
    try:
        print_status(f"🚀 INITIALIZING V67 (REAL DATA) | Mode: {'PAPER' if PAPER_MODE else 'REAL'}")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print_status("✅ Connected.")
    except Exception as e:
        print(f"\n❌ Auth Error: {e}")
        sys.exit()

# --- 1. GET TREND (Spot Price + Futures VWAP) ---
def get_market_trend():
    try:
        # Get Live Spot Price (LTP)
        # Note: 'exchange_trading_symbols' usually expects a list or specific format. 
        # Using the exact call structure you provided.
        ltp_resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=["NSE-NIFTY"] # Ensure list format if required
        )
        # Parse LTP response structure (It returns a dict of symbol:ltp)
        spot_price = 0
        if ltp_resp:
            # Assuming response like {'NSE-NIFTY': 25641.7}
            spot_price = list(ltp_resp.values())[0]

        # Get Futures for VWAP/Volume (Still valid for Volume Spike)
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        
        if not resp or 'candles' not in resp: return spot_price, 0, 0
        
        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]
        
        df['vp'] = ((df['high'] + df['low'] + df['close']) / 3) * df['volume']
        df['VWAP'] = df['vp'].cumsum() / df['volume'].cumsum()
        
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = df.iloc[-1]['volume'] / vol_avg if vol_avg > 0 else 0
        
        return spot_price, df.iloc[-1]['VWAP'], vol_ratio

    except Exception as e:
        return 0, 0, 0

# --- 2. GET OPTION DATA (Using Chain & Quote) ---
def get_option_real_data(spot_price, opt_type):
    try:
        atm_strike = int(round(spot_price / 50) * 50)
        
        # A. FETCH CHAIN FOR OI (The "Map")
        chain = groww.get_option_chain(
            exchange=groww.EXCHANGE_NSE,
            underlying="NIFTY",
            expiry_date=EXPIRY_DATE
        )
        
        if not chain or 'strikes' not in chain: return None, 0, 0, 0, 0
        
        strike_data = chain['strikes'].get(str(atm_strike))
        if not strike_data: return None, 0, 0, 0, 0
        
        # Get CE or PE data
        opt_data = strike_data.get(opt_type, {})
        symbol = opt_data.get("trading_symbol")
        ltp = opt_data.get("ltp", 0)
        oi = opt_data.get("open_interest", 0) # Real OI from Chain
        
        # B. FETCH QUOTE FOR OI CHANGE (The "Pulse")
        # We need the trading symbol to get the quote
        # Your format: groww.get_quote(..., trading_symbol="NIFTY") was for index
        # We need it for the OPTION symbol to get 'oi_day_change_percentage'
        
        quote = groww.get_quote(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_FNO,
            trading_symbol=symbol # e.g., NIFTY25N1823400CE
        )
        
        oi_chg_pct = 0
        if quote:
            oi_chg_pct = quote.get("oi_day_change_percentage", 0)
            
        return symbol, atm_strike, ltp, oi, oi_chg_pct

    except: return None, 0, 0, 0, 0

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

            # 2. GET TREND
            spot_p, fut_vwap, vol_ratio = get_market_trend()
            if spot_p == 0: 
                print_status("Fetching Spot Price...", end="\r"); time.sleep(1); continue

            # Determine Direction (Spot vs VWAP)
            # Using Futures VWAP as the "Anchor" for Spot Price direction is a common proxy
            # If Spot > Futures VWAP -> Bullish
            trend_mode = "SIDEWAYS"
            target_type = "CE"
            
            if spot_p > fut_vwap:
                trend_mode = "BULLISH"
                target_type = "CE"
            elif spot_p < fut_vwap:
                trend_mode = "BEARISH"
                target_type = "PE"

            # 3. GET OPTION DATA (Real Chain + Quote)
            sym, strike, opt_ltp, opt_oi, oi_chg = get_option_real_data(spot_p, target_type)
            
            # 4. SIGNAL LOGIC
            signal_log = "WAIT"
            
            if position is None and trades_today < MAX_TRADES:
                # Rule: High Volume + Panic OI Drop (Negative Change)
                if (vol_ratio > VOL_MULTIPLIER) and (oi_chg < OI_DROP_THRESHOLD):
                    if trend_mode == "BULLISH" and target_type == "CE":
                         signal_log = "BUY_CE"
                    elif trend_mode == "BEARISH" and target_type == "PE":
                         signal_log = "BUY_PE"

            # 5. LOGGING
            log_heartbeat(trend_mode, spot_p, fut_vwap, vol_ratio, strike, target_type, opt_ltp, opt_oi, oi_chg, signal_log)
            
            # 6. DISPLAY
            disp = f"{trend_mode} | Spot: {spot_p} | {target_type} OI Chg: {oi_chg:.2f}%"
            if position: disp += f" | PnL: {(opt_ltp - entry_price)*LOT_SIZE:.0f}"
            print_status(disp, end="\r")

            # 7. EXECUTION
            if position is None and signal_log in ["BUY_CE", "BUY_PE"]:
                print(f"\n🚀 SIGNAL: {signal_log}! OI Dropped {oi_chg:.2f}%")
                position = target_type
                active_symbol = sym
                entry_price = opt_ltp
                sl_price = entry_price - SL_POINTS
                highest_price = entry_price
                trades_today += 1
                msg = f"✅ BOUGHT {sym} @ {entry_price}"
                print_status(msg)
            
            # 8. MANAGEMENT (Scalper)
            elif position:
                # Re-fetch specific quote for exit price (simplified)
                # In production, call get_quote(active_symbol) here
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
                    position = None

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 Stopped."); break
        except Exception as e:
            print(f"\n⚠️ Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()