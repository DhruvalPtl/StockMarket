# @title V36 - The Stress Tester (Slippage + Taxes)
from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import datetime
import csv
import sys
import os

# --- CONFIGURATION ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ0NDI0MDQsImlhdCI6MTc2NjA0MjQwNCwibmJmIjoxNzY2MDQyNDA0LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhZTY1ODRjMC0yY2ViLTRiNzQtOGJhNi1hOWE3ZDA0NGI3OGRcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJiZjBmNjM2LTcxMWItNDhmYS04M2Y4LWFhMjYwYmFjNDA5OFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjE4NTpjZGM6Y2JhZDo1MDk1LDE3Mi42OS4xNzkuOTYsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ0NDI0MDQyODZ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.DcZojQEm-K8JH1XHXdz3cbI622Qz-APP3nJ3yf_DfAwdqhSqqdYEQYwLP36cUrsAs_RuWd1EZfI0ypTWW7Q9yA"
API_SECRET = "%HHhIe7l9bvm2r^vsS4c^^@VCQOfV^9l"

# 📅 TEST PERIOD
START_DATE = "2025-10-01"
END_DATE = "2025-12-17"

# ⚠️ STRESS PARAMETERS (The "Real World" Friction)
SLIPPAGE_POINTS = 1.0     # Buy 1 pt higher, Sell 1 pt lower
BROKERAGE_PER_ORDER = 50.0 # Approx Brokerage + STT per complete trade

# STRATEGY SETTINGS
CAPITAL = 10000.0
LOT_SIZE = 75
EMA_FAST = 5
EMA_SLOW = 13
SL_POINTS = 5.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0
MAX_OPT_PRICE = 250.0

CSV_FILENAME = f"V36_Stress_Test_trail_trig{TRAIL_TRIGGER}_trail_gap{TRAIL_GAP}_sl{SL_POINTS}.csv"

# --- 1. AUTHENTICATION ---
def get_groww_client():
    try:
        print("🔐 Authenticating...")
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"❌ Auth Failed: {e}")
        sys.exit()

# --- 2. EXPIRY HELPER ---
def get_expiry_map(groww, start_str, end_str):
    s_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d")
    e_dt = datetime.datetime.strptime(end_str, "%Y-%m-%d")

    months_years = set()
    curr = s_dt
    while curr <= e_dt:
        months_years.add((curr.year, curr.month))
        curr += datetime.timedelta(days=1)

    all_expiries = []
    print(f"⏳ Fetching Expiries for Stress Test...")

    for y, m in months_years:
        try:
            resp = groww.get_expiries(exchange=groww.EXCHANGE_NSE, underlying_symbol="NIFTY", year=y, month=m)
            if resp and 'expiries' in resp:
                all_expiries.extend(resp['expiries'])
        except Exception:
            pass

    all_expiries.sort()
    date_map = {}
    curr = s_dt
    while curr <= e_dt:
        curr_str = curr.strftime("%Y-%m-%d")
        found_expiry = None
        for exp in all_expiries:
            if exp >= curr_str:
                found_expiry = exp
                break

        if found_expiry:
            dt_obj = datetime.datetime.strptime(found_expiry, "%Y-%m-%d")
            tag = dt_obj.strftime("%d%b%y")
            date_map[curr_str] = tag

        curr += datetime.timedelta(days=1)
    return date_map

# --- 3. SYMBOL CONSTRUCTOR ---
def construct_symbol_name(expiry_tag, strike, type_):
    return f"NSE-NIFTY-{expiry_tag}-{strike}-{type_}"

# --- 4. DATA FETCHING ---
def fetch_candle_history(groww, symbol, start_str, end_str):
    try:
        segment = groww.SEGMENT_FNO if "CE" in symbol or "PE" in symbol else groww.SEGMENT_CASH
        resp = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE, segment=segment, groww_symbol=symbol,
            start_time=start_str, end_time=end_str, candle_interval=groww.CANDLE_INTERVAL_MIN_1
        )
        if not resp or 'candles' not in resp: return None

        df = pd.DataFrame(resp['candles'])
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if len(df.columns) == 7: cols.append('oi')
        df.columns = cols[:len(df.columns)]

        if isinstance(df['timestamp'].iloc[0], str):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        df.set_index('timestamp', inplace=True)
        df['close'] = df['close'].astype(float)
        return df
    except Exception:
        return None

# --- 5. THE ENGINE (STRESS MODE) ---
def run_v36():
    groww = get_groww_client()
    expiry_map = get_expiry_map(groww, START_DATE, END_DATE)
    if not expiry_map: return

    f = open(CSV_FILENAME, "w", newline='')
    headers = ["Date", "Type", "Strike", "Raw Buy", "Stressed Buy",
               "Raw Sell", "Stressed Sell", "Gross PnL", "Net PnL", "Balance"]
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    current_balance = CAPITAL
    start_dt = datetime.datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(END_DATE, "%Y-%m-%d")

    print(f"\n🔥 STARTING STRESS TEST (Slippage: {SLIPPAGE_POINTS}pts | Charges: ₹{BROKERAGE_PER_ORDER})")

    curr_date = start_dt
    while curr_date <= end_dt:
        test_date = curr_date.strftime("%Y-%m-%d")
        if test_date not in expiry_map:
            curr_date += datetime.timedelta(days=1)
            continue

        tag = expiry_map[test_date]
        print(f"\n📅 {test_date} | Tag: {tag} | Bal: ₹{current_balance:.2f}")

        s_str = (curr_date - datetime.timedelta(days=3)).strftime("%Y-%m-%d 09:15:00")
        e_str = (curr_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d 15:30:00")

        nifty_1m = fetch_candle_history(groww, "NSE-NIFTY", s_str, e_str)
        if nifty_1m is None or nifty_1m.empty:
            curr_date += datetime.timedelta(days=1)
            continue

        nifty_5m = nifty_1m.resample('5min').agg({'close': 'last'}).dropna()
        nifty_5m['EMA_Fast'] = ta.ema(nifty_5m['close'], length=EMA_FAST)
        nifty_5m['EMA_Slow'] = ta.ema(nifty_5m['close'], length=EMA_SLOW)

        day_data = nifty_5m[nifty_5m.index.astype(str).str.contains(test_date)]
        if day_data.empty:
            curr_date += datetime.timedelta(days=1)
            continue

        position = None
        trades_count = 0

        for i in range(1, len(day_data)):
            curr = day_data.iloc[i]
            prev = day_data.iloc[i-1]
            time_curr = day_data.index[i]
            nifty_ltp = curr['close']

            if position is None and trades_count < 5:
                signal_type = None
                if curr['EMA_Fast'] > curr['EMA_Slow'] and prev['EMA_Fast'] <= prev['EMA_Slow']: signal_type = "CE"
                elif curr['EMA_Fast'] < curr['EMA_Slow'] and prev['EMA_Fast'] >= prev['EMA_Slow']: signal_type = "PE"

                if signal_type:
                    strike = int(round(nifty_ltp / 50) * 50)
                    contract_symbol = construct_symbol_name(tag, strike, signal_type)

                    opt_start = time_curr.strftime("%Y-%m-%d %H:%M:%S")
                    opt_end = (time_curr + datetime.timedelta(hours=6)).strftime("%Y-%m-%d 15:30:00")
                    opt_df = fetch_candle_history(groww, contract_symbol, opt_start, opt_end)

                    if opt_df is not None and not opt_df.empty:
                        raw_entry = opt_df.iloc[0]['close']

                        # --- STRESS 1: SLIPPAGE ON ENTRY ---
                        stressed_entry = raw_entry + SLIPPAGE_POINTS

                        if raw_entry > MAX_OPT_PRICE: continue

                        required_margin = stressed_entry * LOT_SIZE
                        if required_margin > current_balance:
                            print(f"   ❌ SKIPPED: Insufficient Funds (Need ₹{required_margin:.0f})")
                            continue

                        # TRADE LOGIC (Based on RAW price, but accounting for stressed entry)
                        sl = raw_entry - SL_POINTS
                        highest = raw_entry
                        raw_exit = 0.0

                        print(f"   🔎 {signal_type} Signal | Raw: {raw_entry} -> Stressed Entry: {stressed_entry}")

                        for j in range(1, len(opt_df)):
                            tick = opt_df.iloc[j]
                            ltp = tick['close']

                            if ltp > highest:
                                highest = ltp
                                if (highest - raw_entry) > TRAIL_TRIGGER:
                                    new_sl = highest - TRAIL_GAP
                                    if new_sl > sl: sl = new_sl

                            if ltp <= sl:
                                raw_exit = sl
                                break

                        if raw_exit == 0.0: raw_exit = opt_df.iloc[-1]['close']

                        # --- STRESS 2: SLIPPAGE ON EXIT ---
                        stressed_exit = raw_exit - SLIPPAGE_POINTS

                        # --- CALC PnL ---
                        gross_pnl = (stressed_exit - stressed_entry) * LOT_SIZE

                        # --- STRESS 3: BROKERAGE ---
                        net_pnl = gross_pnl - BROKERAGE_PER_ORDER

                        current_balance += net_pnl
                        trades_count += 1

                        print(f"      🔴 EXIT Raw: {raw_exit} -> Stressed: {stressed_exit} | Net PnL: {net_pnl:.2f}")

                        writer.writerow({
                            "Date": test_date, "Type": signal_type, "Strike": contract_symbol,
                            "Raw Buy": f"{raw_entry:.2f}", "Stressed Buy": f"{stressed_entry:.2f}",
                            "Raw Sell": f"{raw_exit:.2f}", "Stressed Sell": f"{stressed_exit:.2f}",
                            "Gross PnL": f"{gross_pnl:.2f}", "Net PnL": f"{net_pnl:.2f}",
                            "Balance": f"{current_balance:.2f}"
                        })

        curr_date += datetime.timedelta(days=1)

    f.close()
    print(f"\n💰 FINAL STRESSED BALANCE: ₹{current_balance:.2f}")
    print(f"💾 Stress Log Saved: {CSV_FILENAME}")

if __name__ == "__main__":
    run_v36()