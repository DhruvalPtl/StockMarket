# =========================================

# =========================
# V54 STYLE BACKTEST ENGINE
# =========================

from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import datetime
import csv

# ================= CONFIG =================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ0NDI0MDQsImlhdCI6MTc2NjA0MjQwNCwibmJmIjoxNzY2MDQyNDA0LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhZTY1ODRjMC0yY2ViLTRiNzQtOGJhNi1hOWE3ZDA0NGI3OGRcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJiZjBmNjM2LTcxMWItNDhmYS04M2Y4LWFhMjYwYmFjNDA5OFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjE4NTpjZGM6Y2JhZDo1MDk1LDE3Mi42OS4xNzkuOTYsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ0NDI0MDQyODZ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.DcZojQEm-K8JH1XHXdz3cbI622Qz-APP3nJ3yf_DfAwdqhSqqdYEQYwLP36cUrsAs_RuWd1EZfI0ypTWW7Q9yA"
API_SECRET = "%HHhIe7l9bvm2r^vsS4c^^@VCQOfV^9l"

START_DATE = "2025-10-01"
END_DATE   = "2025-12-17"

CAPITAL = 10000.0
LOT_SIZE = 75
MAX_TRADES_PER_DAY = 5

EMA_FAST = 5
EMA_SLOW = 13

SL_POINTS = 7.0
TRAIL_TRIGGER = 5.0
TRAIL_GAP = 5.0

SLIPPAGE = 1.0
BROKERAGE = 50.0
MAX_OPT_PRICE = 250.0

TRADE_BOOK = f"V54_Backtest_Trades_trail_trig{TRAIL_TRIGGER}_trail_gap{TRAIL_GAP}_sl{SL_POINTS}_updated.csv"

# =========================================

def auth():
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    return GrowwAPI(token)

def get_expiry_tag(groww, date):
    resp = groww.get_expiries(
        exchange=groww.EXCHANGE_NSE,
        underlying_symbol="NIFTY",
        year=date.year,
        month=date.month
    )
    for e in resp.get("expiries", []):
        if e >= date.strftime("%Y-%m-%d"):
            return datetime.datetime.strptime(e, "%Y-%m-%d").strftime("%d%b%y")
    return None

def symbol_name(tag, strike, t):
    return f"NSE-NIFTY-{tag}-{strike}-{t}"

# ================= SAFE CANDLE FETCH =================

def fetch_1m(groww, symbol, s, e, fno=False):
    seg = groww.SEGMENT_FNO if fno else groww.SEGMENT_CASH
    r = groww.get_historical_candles(
        exchange=groww.EXCHANGE_NSE,
        segment=seg,
        groww_symbol=symbol,
        start_time=s,
        end_time=e,
        candle_interval=groww.CANDLE_INTERVAL_MIN_1
    )
    if not r or "candles" not in r or len(r["candles"]) == 0:
        return None

    df = pd.DataFrame(r["candles"])

    if isinstance(df.columns[0], int):
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        if len(df.columns) == 7:
            cols.append("oi")
        df.columns = cols[:len(df.columns)]
    else:
        df.rename(columns={"ts": "timestamp", "time": "timestamp"}, inplace=True)

    if isinstance(df["timestamp"].iloc[0], str):
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

    df.set_index("timestamp", inplace=True)
    df["c"] = df["close"].astype(float)

    return df

# ================= SMART STRIKE =================

def smart_strike(groww, tag, nifty, t, capital, candle_time):
    strike = int(round(nifty / 50) * 50)
    start = candle_time.strftime("%Y-%m-%d %H:%M:%S")
    end   = (candle_time + datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")

    for _ in range(5):
        sym = symbol_name(tag, strike, t)
        df = fetch_1m(groww, sym, start, end, True)
        if df is not None and not df.empty:
            price = df.iloc[0]["c"]
            if price > 5 and price * LOT_SIZE <= capital:
                return sym, price
        strike += 50 if t == "CE" else -50

    return None, None

# ================= BACKTEST =================

def run():
    groww = auth()
    bal = CAPITAL

    with open(TRADE_BOOK, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Date",
            "Entry_Time", "Exit_Time",
            "Type", "Symbol",
            "Nifty_Entry", "Nifty_Exit",
            "Opt_Entry", "Opt_Exit",
            "GrossPnL", "NetPnL",
            "Balance", "Reason"
        ])

        d = datetime.datetime.strptime(START_DATE, "%Y-%m-%d")
        end = datetime.datetime.strptime(END_DATE, "%Y-%m-%d")

        while d <= end:
            date = d.strftime("%Y-%m-%d")
            print(f"\n📅 {date} | Balance ₹{bal:.2f}")

            tag = get_expiry_tag(groww, d)
            if not tag:
                d += datetime.timedelta(days=1)
                continue

            nifty = fetch_1m(
                groww,
                "NSE-NIFTY",
                f"{date} 09:15:00",
                f"{date} 15:30:00"
            )
            if nifty is None:
                d += datetime.timedelta(days=1)
                continue

            nifty5 = nifty.resample("5min").agg({"c": "last"}).dropna()
            nifty5["EMA_F"] = ta.ema(nifty5["c"], EMA_FAST)
            nifty5["EMA_S"] = ta.ema(nifty5["c"], EMA_SLOW)

            trades = 0

            for i in range(1, len(nifty5)):
                curr = nifty5.iloc[i]
                prev = nifty5.iloc[i-1]
                ltp = curr["c"]

                if curr.name.time() >= datetime.time(15, 20):
                    continue

                sig = None
                ema_diff = curr["EMA_F"] - curr["EMA_S"]
                prev_diff = prev["EMA_F"] - prev["EMA_S"]

                if curr["EMA_F"] > curr["EMA_S"] and prev["EMA_F"] <= prev["EMA_S"]:
                    sig = "CE"
                elif curr["EMA_F"] < curr["EMA_S"] and prev["EMA_F"] >= prev["EMA_S"]:
                    sig = "PE"
                elif (
                    curr["EMA_F"] > curr["EMA_S"]
                    and ema_diff > 2
                    and prev["c"] < prev["EMA_F"]
                    and curr["c"] > curr["EMA_F"]
                    and ema_diff > prev_diff
                ):
                    sig = "CE"
                elif (
                    curr["EMA_F"] < curr["EMA_S"]
                    and ema_diff < -2
                    and prev["c"] > prev["EMA_F"]
                    and curr["c"] < curr["EMA_F"]
                    and ema_diff < prev_diff
                ):
                    sig = "PE"

                if sig and trades < MAX_TRADES_PER_DAY:
                    entry_time = curr.name + datetime.timedelta(minutes=5)
                    nifty_entry = ltp
                    
                    # Stop if we are past market close
                    if entry_time.time() >= datetime.time(15, 25):
                        continue
                    
                    sym, raw_entry = smart_strike(
                        groww, tag, ltp, sig, bal, entry_time
                    )
                    if not sym or raw_entry > MAX_OPT_PRICE:
                        continue

                    opt_start = entry_time
                    opt_end = datetime.datetime.strptime(
                        f"{date} 15:30:00", "%Y-%m-%d %H:%M:%S"
                    )
                    if opt_start >= opt_end:
                        continue

                    opt = fetch_1m(
                        groww,
                        sym,
                        opt_start.strftime("%Y-%m-%d %H:%M:%S"),
                        opt_end.strftime("%Y-%m-%d %H:%M:%S"),
                        True
                    )
                    if opt is None:
                        continue

                    entry = raw_entry + SLIPPAGE
                    sl = raw_entry - SL_POINTS
                    high = raw_entry
                    exit_p = None
                    exit_time = None
                    nifty_exit = None
                    reason = "EOD"

                    for ts, r in opt.iterrows():
                        p = r["c"]
                        if p > high:
                            high = p
                            if high - raw_entry > TRAIL_TRIGGER:
                                sl = max(sl, high - TRAIL_GAP)
                        if p <= sl:
                            exit_p = sl
                            exit_time = ts
                            nifty_exit = nifty.loc[:ts].iloc[-1]["c"]
                            reason = "SL/TRAIL"
                            break

                    if exit_p is None:
                        exit_p = opt.iloc[-1]["c"]
                        exit_time = opt.index[-1]
                        nifty_exit = nifty.loc[:exit_time].iloc[-1]["c"]

                    exit_s = exit_p - SLIPPAGE
                    gross = (exit_s - entry) * LOT_SIZE
                    net = gross - BROKERAGE
                    bal += net
                    trades += 1

                    writer.writerow([
                        date,
                        entry_time.strftime("%H:%M:%S"),
                        exit_time.strftime("%H:%M:%S"),
                        sig, sym,
                        round(nifty_entry, 2),
                        round(nifty_exit, 2),
                        round(entry, 2),
                        round(exit_s, 2),
                        round(gross, 2),
                        round(net, 2),
                        round(bal, 2),
                        reason
                    ])

            d += datetime.timedelta(days=1)

    print("\n✅ BACKTEST COMPLETE")

# ================= RUN =================
if __name__ == "__main__":
    run()
