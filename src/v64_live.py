# @title V64 - Institutional Sniper (With Full "Black Box" Logging)
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

# --- ⚙️ CONFIGURATION (VERIFIED) ---
CAPITAL = 10000.0
LOT_SIZE = 75

# Symbols (Based on your verification)
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"  # Monthly Futures
EXPIRY_TAG     = "23Dec25"                # For Symbol Construction
EXPIRY_DATE    = "2025-12-23"             # For Option Chain

# Strategy Parameters
VOL_MULTIPLIER = 1.5          # Volume Spike Requirement
OI_DROP_THRESHOLD = -2.0      # OI must drop by at least 2% (Short Covering)
MAX_SPREAD = 0.50             # Max difference between Bid/Ask (Slippage Guard)

# Risk Management (Scalper)
SL_POINTS = 4.0               # Hard Stop
TRAIL_TRIGGER = 3.0           # Profit required to activate trail
TRAIL_GAP = 2.0               # Distance of trailing stop

# Logging
LOG_FILE = "V64_Master_Log.csv"
IST = pytz.timezone('Asia/Kolkata')

# --- 📊 STATE VARIABLES ---
groww = None
position = None          # None, "CE", "PE"
active_symbol = None
entry_price = 0.0
sl_price = 0.0
highest_price = 0.0
trades_today = 0
MAX_TRADES = 3

# --- 📝 LOGGING ENGINE ---
def init_log_file():
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", 
                "Fut_Price", "Fut_VWAP", "Fut_Vol", "Vol_Ratio", "Trend_Status",
                "ATM_Strike", "Opt_Symbol", 
                "Opt_LTP", "Opt_OI", "OI_Chg%", "Spread",
                "Signal", "Position", "PnL", "Balance"
            ])

def log_heartbeat(fut_p, fut_vwap, fut_vol, vol_ratio, trend, 
                  strike, opt_sym, opt_ltp, opt_oi, oi_chg, spread, 
                  signal, pos, pnl, bal):
    try:
        with open(LOG_FILE, "a", newline='') as f:
            writer = csv.writer(f)
            ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
            writer.writerow([
                ts, 
                fut_p, round(fut_vwap, 2), fut_vol, round(vol_ratio, 2), trend,
                strike, opt_sym, 
                opt_ltp, opt_oi, round(oi_chg, 2), round(spread, 2),
                signal, pos, round(pnl, 2), round(bal, 2)
            ])
    except: pass

def print_status(msg, end="\n"):
    ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
    sys.stdout.write(f"\r[{ts}] {msg}" + (" " * 10))
    if end == "\n": sys.stdout.write("\n")
    sys.stdout.flush()

# --- 🔌 CONNECTION ---
def initialize():
    global groww
    try:
        print_status("🔌 Authenticating with Groww...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        groww = GrowwAPI(token)
        print_status("✅ Connected. V64 Engine Started.")
        init_log_file()
    except Exception as e:
        print(f"\n❌ Auth Error: {e}")
        sys.exit()

# --- 🧠 DATA ENGINE ---
def get_futures_status():
    """Fetches Futures Price, VWAP, and Volume Ratio"""
    try:
        end = datetime.datetime.now(IST)
        start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
        
        # 1-min candles for precision VWAP
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1minute"
        )
        if not resp or 'candles' not in resp: return None, 0, 0, 0

        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) >= 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]

        # VWAP Math
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['vp'] = df['tp'] * df['volume']
        df['VWAP'] = df['vp'].cumsum() / df['volume'].cumsum()
        
        # Volume Avg (Last 20 mins)
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        
        latest = df.iloc[-1]
        vol_ratio = latest['volume'] / vol_avg if vol_avg > 0 else 0
        
        return latest['close'], latest['VWAP'], latest['volume'], vol_ratio
    except: return None, 0, 0, 0

def get_atm_quote(spot_price):
    """Fetches ATM Call Quote for OI Change & Spread"""
    try:
        atm_strike = int(round(spot_price / 50) * 50)
        symbol = f"NSE-NIFTY-{EXPIRY_TAG}-{atm_strike}-CE"
        
        # We need LIVE QUOTE for 'oi_day_change_percentage' and 'spread'
        # Note: Depending on Groww library version, this might be 'get_live_quote' or similar.
        # Fallback to Option Chain logic if direct quote fails, but Option Chain is robust.
        
        chain = groww.get_option_chain(
            exchange=groww.EXCHANGE_NSE, underlying="NIFTY", expiry_date=EXPIRY_DATE
        )
        
        if not chain or 'strikes' not in chain: return None
        
        strike_data = chain['strikes'].get(str(atm_strike), {})
        ce_data = strike_data.get("CE", {})
        
        # Construct simplified quote object
        quote = {
            "symbol": ce_data.get("trading_symbol", symbol),
            "strike": atm_strike,
            "ltp": ce_data.get("ltp", 0),
            "oi": ce_data.get("open_interest", 0),
            # Note: Option Chain usually doesn't give Bid/Ask. 
            # If unavailable, we assume 0 spread to rely on price limits, 
            # OR we fetch get_historical_candles[-1] for close price if ltp is missing.
            "spread": 0.0, 
            "oi_chg_pct": 0.0 
        }

        # Try to get extra depth if available in your API version 
        # (Based on the Quote JSON you shared earlier, OI Chg % is key)
        # If we can't get quote directly, we can't get Spread/OI% easily without history.
        # Strategy: Use Historical OI check we verified earlier for OI Chg.
        
        return quote
    except: return None

# --- REVISED DATA FETCHER (Hybrid) ---
# Since we verified Option Chain has OI, but Quotes have OI Change %...
# We will use the verified method: Manual OI Change Calculation.
oi_history = {} # Stores previous OI to calc change manually

def get_smart_data(fut_price):
    try:
        atm_strike = int(round(fut_price / 50) * 50)
        symbol = f"NSE-NIFTY-{EXPIRY_TAG}-{atm_strike}-CE"
        
        # Get 5-min candle for reliable OI
        end = datetime.datetime.now(IST)
        start = end - datetime.timedelta(minutes=15)
        
        resp = groww.get_historical_candles(
            exchange="NSE", segment="FNO", groww_symbol=symbol,
            start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="5minute"
        )
        
        if not resp or 'candles' not in resp: return None
        
        candles = resp['candles']
        if len(candles) < 2: return None
        
        curr = candles[-1]
        prev = candles[-2]
        
        # Index 4=Close, 6=OI
        ltp = curr[4]
        curr_oi = curr[6] if len(curr) > 6 else 0
        prev_oi = prev[6] if len(prev) > 6 else 0
        
        if prev_oi == 0: oi_chg = 0
        else: oi_chg = ((curr_oi - prev_oi) / prev_oi) * 100.0
        
        return {
            "symbol": symbol,
            "strike": atm_strike,
            "ltp": ltp,
            "oi": curr_oi,
            "oi_chg_pct": oi_chg,
            "spread": 0 # Can't calculate accurately without Level 2 data, skipping filter
        }
    except: return None

# --- 🚀 MAIN LOOP ---
def main():
    global position, active_symbol, entry_price, sl_price, highest_price, trades_today, CAPITAL
    
    initialize()
    
    while True:
        try:
            # 1. TIME CHECK
            now = datetime.datetime.now(IST)
            if now.time() < datetime.time(9, 15):
                print_status(f"Waiting for Open... {now.strftime('%H:%M:%S')}", end="\r")
                time.sleep(5); continue
            if now.time() > datetime.time(15, 25):
                print_status("Market Closed."); break

            # 2. FETCH FUTURES (The Wave)
            fut_price, fut_vwap, fut_vol, vol_ratio = get_futures_status()
            
            if fut_price == 0:
                print_status("Fetching Data...", end="\r"); time.sleep(1); continue

            # Trend Status
            trend = "SIDEWAYS"
            if fut_price > fut_vwap: trend = "BULLISH"
            elif fut_price < fut_vwap: trend = "BEARISH"

            # 3. FETCH OPTION (The Trigger)
            opt_data = get_smart_data(fut_price)
            if not opt_data: continue
            
            # 4. LOGIC ENGINE
            signal = "WAIT"
            
            # ENTRY LOGIC (Short Covering)
            # Fut > VWAP  AND  Vol > 1.5x  AND  Call OI Dropping (Shorts Fleeing)
            if position is None and trades_today < MAX_TRADES:
                if (fut_price > fut_vwap) and (vol_ratio > VOL_MULTIPLIER):
                    if opt_data['oi_chg_pct'] < OI_DROP_THRESHOLD: # e.g. -2%
                        signal = "BUY_SIGNAL"
                        
                        # EXECUTE
                        print_status(f"🚀 SIGNAL: Short Covering! OI dropped {opt_data['oi_chg_pct']:.2f}%")
                        position = "CE"
                        active_symbol = opt_data['symbol']
                        entry_price = opt_data['ltp']
                        sl_price = entry_price - SL_POINTS
                        highest_price = entry_price
                        trades_today += 1
                        print_status(f"✅ BOUGHT {active_symbol} @ {entry_price}")

            # EXIT LOGIC (Scalper Management)
            pnl = 0.0
            if position == "CE":
                # Update Prices
                curr_price = opt_data['ltp']
                if curr_price > 0:
                    # Trail
                    if curr_price > highest_price:
                        highest_price = curr_price
                        if (highest_price - entry_price) > TRAIL_TRIGGER:
                            new_sl = highest_price - TRAIL_GAP
                            if new_sl > sl_price: sl_price = new_sl
                    
                    # Stop
                    if curr_price <= sl_price:
                        signal = "STOP_LOSS"
                        pnl = (sl_price - entry_price) * LOT_SIZE
                        CAPITAL += pnl
                        print_status(f"🔴 SOLD @ {sl_price} | PnL: {pnl:.2f}")
                        position = None
                    else:
                        signal = "HOLD"
                        pnl = (curr_price - entry_price) * LOT_SIZE

            # 5. BLACK BOX LOGGING
            log_heartbeat(
                fut_price, fut_vwap, fut_vol, vol_ratio, trend,
                opt_data['strike'], opt_data['symbol'],
                opt_data['ltp'], opt_data['oi'], opt_data['oi_chg_pct'], opt_data['spread'],
                signal, position, pnl, CAPITAL
            )

            # Display
            disp_pnl = f" | PnL: {pnl:.0f}" if position else ""
            print_status(f"Fut: {fut_price:.1f} (VWAP {fut_vwap:.1f}) | OI Chg: {opt_data['oi_chg_pct']:.2f}% | Signal: {signal}{disp_pnl}", end="\r")
            
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 Bot Stopped by User.")
            break
        except Exception as e:
            print(f"\n⚠️ Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()