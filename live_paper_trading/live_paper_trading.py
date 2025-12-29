# @title V54 - Live Bot with Continuous Price Tracking
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
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ3ODA1MzAsImlhdCI6MTc2NjM4MDUzMCwibmJmIjoxNzY2MzgwNTMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIzNTcyN2Q0MC0yNzdlLTQ3NWQtOGFiOC1mZGZmMjExNWIyODlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjE4YWNjY2FmLWRlY2ItNGMxYi04MDBkLThhMWYyN2U2YjhlNVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjY4Yzk6OWQ4NToyNThlOjI2YywxNjIuMTU4LjUxLjE3NCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDc4MDUzMDgxOH0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.0zQsgYyp3GYSVyIXkYrhRlRS0QXbl7FBWnGI7NS3gTekZmEkE6WmL23BCR4VSd0T7ASPEfdaHydwK-f2--hE5g"
API_SECRET = "P!zaa_W**OivPuTI0%mV7_ixnV3l^Ak%"

# --- CONFIGURATION ---
CAPITAL = 10000.0
LOT_SIZE = 75
EXPIRY_TAG = "30Dec25"
MAX_TRADES = 100

# STRATEGY
EMA_FAST = 5
EMA_SLOW = 13
SL_POINTS = 5.0
TRAIL_TRIGGER = 4.0
TRAIL_GAP = 3.0

# SYSTEM
IST = pytz.timezone('Asia/Kolkata')
_ts = datetime.datetime.now(IST).strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"D:\\StockMarket\\StockMarket\\live_paper_trading\\log\\Live_System_Log_{_ts}.txt"
TRACKER_FILE = f"D:\\StockMarket\\StockMarket\\live_paper_trading\\log\\Live_Super_Tracker_{_ts}.csv"
TRADE_BOOK = f"D:\\StockMarket\\StockMarket\\live_paper_trading\\trade_book\\Live_Trade_Book_{_ts}.csv"

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
            # Write Header if new file (ADDED "EMA_Diff")
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

            # Added fmt(diff) to the row
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
        print("✅ Auth Success.")
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
        start = end - datetime.timedelta(days=10)
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

        if isinstance(df['timestamp'].iloc[0], str): df['timestamp'] = pd.to_datetime(df['timestamp'])
        else: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        df.set_index('timestamp', inplace=True)
        df['close'] = df['close'].astype(float)

        df_5m = df.resample('5min').agg({'close': 'last'}).dropna()
        if len(df_5m) < 50: return None, None

        df_5m['EMA_Fast'] = ta.ema(df_5m['close'], length=EMA_FAST)
        df_5m['EMA_Slow'] = ta.ema(df_5m['close'], length=EMA_SLOW)

        return df_5m.iloc[-1], df_5m.iloc[-2]
    except: return None, None

def get_affordable_symbol(nifty_ltp, type_, capital):
    """
    Finds a strike price that fits your budget.
    Starts at ATM, then moves OTM (Out of The Money) if too expensive.
    """
    # Start at ATM
    strike = int(round(nifty_ltp / 50) * 50)

    # Try up to 5 strikes away (OTM)
    for i in range(5):
        # Construct Symbol
        symbol = construct_symbol(strike, type_)
        price = get_candle_price(symbol)

        # Check if Valid & Affordable
        cost = price * LOT_SIZE
        if price > 5.0 and cost <= capital:
            return symbol, price, strike

        # If too expensive, move OTM
        if type_ == "CE":
            strike += 50  # Call OTM is higher
        else:
            strike -= 50  # Put OTM is lower

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
            # <--- ADD THIS LINE HERE ---
            current_diff = ema_f - ema_s

            # --- PREPARE DATA FOR LOGGING ---
            target_strike = int(round(nifty_ltp / 50) * 50)

            # Determine Watchlist Symbol (Even if not buying yet)
            # If Trend is Up (Fast > Slow) -> Watch Call (CE)
            # If Trend is Down -> Watch Put (PE)
            watch_type = "CE" if ema_f > ema_s else "PE"
            watch_symbol = construct_symbol(target_strike, watch_type)

            # Always Fetch Price
            live_opt_price = get_candle_price(watch_symbol)

            # Current State Variables
            status_display = "SCANNING"
            reason_display = "WAIT"
            symbol_display = watch_symbol # Show what we are watching

            # If Holding, overwrite with actual trade data
            if position:
                # We update live_opt_price to be the ACTIVE symbol price
                live_opt_price = get_candle_price(active_symbol)

                status_display = "HOLDING"
                reason_display = f"{position}"
                symbol_display = active_symbol

                pnl = (live_opt_price - entry_price) * LOT_SIZE
                sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] Nifty: {nifty_ltp:.1f} | {active_symbol}: {live_opt_price} | PnL: {pnl:.0f}   ")

            # If Scanning
            else:
                diff = ema_f - ema_s
                reason_display = f"WATCH_{watch_type}"
                sys.stdout.write(f"\r[{now.strftime('%H:%M:%S')}] Nifty: {nifty_ltp:.1f} | Watch: {watch_type} {target_strike} @ {live_opt_price} | Diff: {diff:.2f}   ")

            sys.stdout.flush()

            # ** 📝 LOG SUPER TRACKER (Regular Pulse) **
            log_super_tracker(
                status_display, nifty_ltp, ema_f, ema_s, current_diff, target_strike, symbol_display, # <--- Added current_diff
                live_opt_price, entry_price, 0.0,
                nifty_entry_val, 0.0,
                CAPITAL, daily_pnl, reason_display
            )

            # --- ENTRY LOGIC ---
            # --- IMPROVED ENTRY LOGIC (Catch the Rally) ---
            # --- UPDATED V56 ENTRY LOGIC (Smarter Backtest Style) ---
            if position is None and trades_today < MAX_TRADES:
                sig_type = None
                
                # Calculate Acceleration
                prev_diff = prev_f - prev_s
                
                # 1. CLASSIC CROSSOVER
                if ema_f > ema_s and prev_f <= prev_s: sig_type = "CE"
                elif ema_f < ema_s and prev_f >= prev_s: sig_type = "PE"
                
                # 2. SMARTER RALLY CATCHER (From Backtest)
                # Buy Call if: Trend Up + Dip Bounce + Strong (>2) + Accelerating
                elif (ema_f > ema_s) and (current_diff > 2.0) and \
                     (prev['close'] < prev['EMA_Fast']) and (curr['close'] > ema_f) and \
                     (current_diff > prev_diff):
                    sig_type = "CE"
                
                # Buy Put if: Trend Down + Pop Drop + Strong (<-2) + Accelerating (more negative)
                elif (ema_f < ema_s) and (current_diff < -2.0) and \
                     (prev['close'] > prev['EMA_Fast']) and (curr['close'] < ema_f) and \
                     (current_diff < prev_diff):
                    sig_type = "PE"

                if sig_type:
                    # USE SMART SHOPPER HERE
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
                    else:
                         # Log reason for skipping
                         pass

            # --- EXIT LOGIC ---
            elif position:
                if live_opt_price <= 0: continue

                # Trail
                if live_opt_price > highest_price:
                    highest_price = live_opt_price
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

                    # 1. Log Final Trade to Book
                    log_trade_book(
                        entry_time_str, now.strftime("%H:%M:%S"), position, active_symbol,
                        entry_price, exit_price,
                        nifty_entry_val, nifty_ltp,
                        ema_fast_entry, ema_slow_entry,
                        trade_pnl, CAPITAL, reason
                    )

                    # 2. Log Exit Event to Super Tracker
                    log_super_tracker(
                        "SOLD", nifty_ltp, ema_f, ema_s, current_diff, target_strike, active_symbol, # <--- Added current_diff
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