
"""
groww_polish_collector.py
Polished single-file Groww SDK data collector for NIFTY spot + ATM option LTP + option-chain snapshots.

How to use:
  1. pip install growwapi pandas python-dateutil
  2. Edit CONFIG below (USER_API_KEY, USER_SECRET, OPTIONALS)
  3. Run: python groww_polish_collector.py

Outputs (appended):
  - nifty_spot_1m.csv    (historical backfill; columns: timestamp, open, high, low, close, volume)
  - option_ltp_1m.csv    (minute-aggregated LTPs; columns: timestamp, nifty_ltp, atm_ce_ltp, atm_pe_ltp)
  - option_chain_1m.csv  (snapshot rows per strike per minute)
"""

import os, sys, time, csv, traceback, json
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd

# --------------------------- CONFIG ---------------------------
# Fill these with your Groww credentials
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0NTMwOTcsImlhdCI6MTc2NTA1MzA5NywibmJmIjoxNzY1MDUzMDk3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI1OTliNjk2MS0wYjdjLTRjMTItOTI2OS1lMmVhNzE3ZGEwNWZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjFlNTdhYjE2LWMyMTAtNGJjYS05OWU3LTBhMmEwN2Q0Y2QzM1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmU5MDU6OTgwNTplZDJmOjIxODAsMTcyLjcwLjE4My4xNjQsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0NTMwOTczMzB9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.RxYxyZ2wtnpDxjQzeYuyHTTfNnNp8Z2EmafdaPFWs-_sldXi_9xtkNwBrRErRlVZMIsyRyjlsny8UNkXiEj4mA"
API_SECRET = "Bsm7hh!otvO-JFa9kD5eFt!pbfc1-DT8"
USER_API_KEY = API_KEY
USER_SECRET = API_SECRET


# Files
OUT_SPOT  = "nifty_spot_1m.csv"
OUT_LTP   = "option_ltp_1m.csv"
OUT_CHAIN = "option_chain_1m.csv"
INSTR_CSV = "groww_instruments.csv"

# Behavior
BACKFILL_DAYS = 30          # historical days to backfill (set 0 to skip)
POLL_SECONDS   = 10         # quote poll every X seconds, aggregated to 1-min rows
CHAIN_POLL_SECONDS = 60     # option-chain snapshot frequency (respect API limits)
MARKET_TZ = "Asia/Kolkata"
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# Underlying / symbols used by Groww SDK
GROWW_UNDERLYING_SYMBOL = "NSE-NIFTY"   # format observed from your test
# You can override expiry if you want a particular expiry
OPTION_CHAIN_EXPIRY = None  # e.g. "2025-12-11" or None for nearest

# Convenience test mode: if True, collector will run regardless of market hours (set for testing)
TEST_MODE = False

# --------------------------------------------------------------

# validate keys
if USER_API_KEY.startswith("REPLACE") or USER_SECRET.startswith("REPLACE"):
    print("Please set USER_API_KEY and USER_SECRET in the script and re-run.")
    sys.exit(1)

# timezone helpers
TZ_LOCAL = tz.gettz(MARKET_TZ)
def now_local():
    return datetime.now(TZ_LOCAL)
def iso(ts=None):
    return (ts or now_local()).isoformat()

# import SDK
try:
    from growwapi import GrowwAPI
except Exception as e:
    print("Error: failed to import growwapi SDK. Install it into your virtualenv: pip install growwapi")
    raise

# auth & client
print("Ready to Groww!")
access_token = None
try:
    access_token = GrowwAPI.get_access_token(api_key=USER_API_KEY, secret=USER_SECRET)
except Exception:
    # Some SDKs use different naming; try calling constructor directly with key/secret as fallback
    try:
        access_token = None
    except Exception:
        pass

if access_token is None:
    # try to continue if the SDK allows direct init with API key/secret - handle both cases
    try:
        client = GrowwAPI(USER_API_KEY)  # if SDK accepts token-like string, try
        print("[WARN] Using GrowwAPI(USER_API_KEY) fallback. If this fails, please use get_access_token.")
    except Exception:
        # final attempt: call get_access_token must work; otherwise bail with helpful message
        print("Failed to obtain access token via GrowwAPI.get_access_token(). Check credentials and SDK version.")
        raise SystemExit(1)
else:
    client = GrowwAPI(access_token)

# Short alias to match previous conversation
groww = client

# ---------------- util I/O helpers ----------------
def ensure_csv_header(path, header):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)

def append_row(path, row):
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# ---------------- parse helpers ----------------
def parse_timestamp_ms_or_iso(v):
    try:
        # numeric ms
        if isinstance(v, (int, float)):
            return pd.to_datetime(int(v), unit='ms').tz_localize('UTC').tz_convert(TZ_LOCAL)
        # string ISO
        return pd.to_datetime(v).tz_localize(TZ_LOCAL) if pd.to_datetime(v).tz.tzname(None) is None else pd.to_datetime(v)
    except Exception:
        try:
            return pd.to_datetime(v)
        except:
            return None

def safe_get(d, *keys):
    for k in keys:
        if not d: continue
        if isinstance(d, dict) and k in d:
            return d[k]
    return None

# ---------------- backfill historical spot ----------------
def backfill_nifty_spot(days=BACKFILL_DAYS):
    """
    Robust backfill that accepts:
      - integer-ms timestamps
      - ISO timestamp strings (e.g. '2025-11-07T09:00:00')
      - dict/list response shapes
    Saves OUT_SPOT as CSV (overwrites).
    """
    if days <= 0:
        print("[BACKFILL] Skipping backfill (days <= 0).")
        return

    print(f"[{iso()}] Backfilling NIFTY {days} days 1-min candles (robust parser)...")
    end_dt = now_local()
    start_dt = end_dt - timedelta(days=days)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_str   = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        resp = groww.get_historical_candles(
            groww_symbol=GROWW_UNDERLYING_SYMBOL,
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            start_time=start_str,
            end_time=end_str,
            candle_interval="1minute"
        )
    except Exception:
        print("[BACKFILL][ERROR] historical call failed; printing traceback:")
        traceback.print_exc()
        return

    data = resp
    rows = []

    def parse_ts_val(v):
        # Accept int ms, numeric string ms, ISO string, pandas-parsable
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return pd.to_datetime(int(v), unit='ms').tz_localize('UTC').tz_convert(TZ_LOCAL)
            # numeric string (ms)
            if isinstance(v, str) and v.isdigit():
                return pd.to_datetime(int(v), unit='ms').tz_localize('UTC').tz_convert(TZ_LOCAL)
            # ISO-like string or other timestamp string
            try:
                dt = pd.to_datetime(v)
                # if timezone-naive, localize to MARKET_TZ
                if dt.tzinfo is None:
                    dt = dt.tz_localize(TZ_LOCAL)
                return dt
            except Exception:
                return None
        except Exception:
            return None

    try:
        # Case A: dict with 'candles'
        if isinstance(data, dict) and 'candles' in data:
            cand = data['candles']
            for c in cand:
                # list-of-lists: [ts,o,h,l,c,vol]
                if isinstance(c, (list, tuple)):
                    ts_raw = c[0]
                    ts_dt = parse_ts_val(ts_raw)
                    o = c[1] if len(c) > 1 else None
                    h = c[2] if len(c) > 2 else None
                    l = c[3] if len(c) > 3 else None
                    cl = c[4] if len(c) > 4 else None
                    vol = c[5] if len(c) > 5 else None
                    rows.append([ts_dt.isoformat() if ts_dt is not None else ts_raw, o, h, l, cl, vol])
                elif isinstance(c, dict):
                    ts_raw = safe_get(c, 'timestamp','ts','time')
                    ts_dt = parse_ts_val(ts_raw)
                    rows.append([ts_dt.isoformat() if ts_dt is not None else ts_raw,
                                 c.get('open'), c.get('high'), c.get('low'), c.get('close'), c.get('volume')])
        # Case B: dict with 'data' or 'records'
        elif isinstance(data, dict) and ('data' in data or 'records' in data):
            cand = data.get('data') or data.get('records')
            if isinstance(cand, list):
                for c in cand:
                    ts_raw = safe_get(c, 'timestamp','ts','time')
                    ts_dt = parse_ts_val(ts_raw)
                    rows.append([ts_dt.isoformat() if ts_dt else ts_raw, c.get('open'), c.get('high'), c.get('low'), c.get('close'), c.get('volume')])
        # Case C: list of dicts
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            for c in data:
                ts_raw = safe_get(c, 'timestamp','ts','time')
                ts_dt = parse_ts_val(ts_raw)
                rows.append([ts_dt.isoformat() if ts_dt else ts_raw, c.get('open'), c.get('high'), c.get('low'), c.get('close'), c.get('volume')])
        else:
            print("[BACKFILL][WARN] Unrecognized historical response shape. Printing snippet:")
            print(json.dumps(data)[:2000])
            return
    except Exception:
        print("[BACKFILL][ERROR] Exception while normalizing historical response:")
        traceback.print_exc()
        return

    if not rows:
        print("[BACKFILL] No rows parsed from historical response.")
        return

    # Normalize to DataFrame — try to coerce numeric values
    df = pd.DataFrame(rows, columns=['timestamp','open','high','low','close','volume'])
    # try to convert numeric columns
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.sort_values('timestamp').reset_index(drop=True)
    df.to_csv(OUT_SPOT, index=False)
    print(f"[{iso()}] Backfill saved to {OUT_SPOT} ({len(df)} rows).")


# ---------------- instruments caching ----------------
def fetch_and_cache_instruments():
    """
    Robust instruments loader:
     - tries several common SDK method names
     - tries groww.get_instruments(exchange=...)
     - falls back to reading groww_instruments.csv if present
    Returns instruments list or None.
    """
    print(f"[{iso()}] Fetching instruments list (robust loader)...")
    # 1) try reading local CSV if exists (fastest fallback)
    if os.path.exists(INSTR_CSV):
        try:
            df_local = pd.read_csv(INSTR_CSV)
            print(f"[{iso()}] Loaded instruments from local CSV {INSTR_CSV} ({len(df_local)} rows).")
            return df_local.to_dict(orient='records')
        except Exception:
            print("[INSTR] failed to load local instruments CSV; will try SDK calls.")

    candidate_methods = [
        ('get_instruments', {'exchange': getattr(groww, 'EXCHANGE_NSE', None)}),
        ('get_all_instruments', {}),
        ('get_instrument_list', {}),
        ('instruments', {}),
        ('fetch_instruments', {}),
        ('download_instruments', {}),
        ('get_exchange_instruments', {'exchange': getattr(groww, 'EXCHANGE_NSE', None)}),
    ]

    instruments = None
    for name, kwargs in candidate_methods:
        if not hasattr(groww, name):
            continue
        func = getattr(groww, name)
        try:
            if kwargs:
                # filter out None values
                kw = {k:v for k,v in kwargs.items() if v is not None}
                resp = func(**kw)
            else:
                resp = func()
            # normalize
            if isinstance(resp, dict) and 'data' in resp:
                instruments = resp['data']
            elif isinstance(resp, dict) and 'records' in resp:
                instruments = resp['records']
            else:
                instruments = resp
            print(f"[INSTR][DEBUG] Fetched instruments using SDK method: {name} (rows: {len(instruments) if isinstance(instruments, list) else 'unknown'})")
            break
        except TypeError:
            # signature mismatch — try without kwargs
            try:
                resp = func()
                if isinstance(resp, dict) and 'data' in resp:
                    instruments = resp['data']
                else:
                    instruments = resp
                print(f"[INSTR][DEBUG] Fetched instruments using SDK method (no args): {name}")
                break
            except Exception as e_inner:
                print(f"[INSTR][DEBUG] method {name} failed:", str(e_inner)[:200])
                continue
        except Exception as e:
            print(f"[INSTR][DEBUG] method {name} raised:", type(e).__name__, str(e)[:200])
            continue

    # fallback: attribute groww.instruments
    if instruments is None and hasattr(groww, 'instruments'):
        try:
            inst_attr = getattr(groww, 'instruments')
            if isinstance(inst_attr, (list, dict)):
                instruments = inst_attr if isinstance(inst_attr, list) else inst_attr.get('data', inst_attr)
                print("[INSTR][DEBUG] Loaded instruments from groww.instruments attribute.")
        except Exception:
            pass

    if instruments is None:
        print("[INSTR][WARN] Could not fetch instruments via SDK. Two options:")
        print("  1) Export instruments CSV from Groww console and save it as", INSTR_CSV)
        print("  2) Paste the output of this command here: print([m for m in dir(groww) if 'instrument' in m.lower() or 'instruments' in m.lower()])")
        return None

    # normalize and save CSV
    try:
        df = pd.DataFrame(instruments)
        df.to_csv(INSTR_CSV, index=False)
        print(f"[{iso()}] Instruments cached to {INSTR_CSV} ({len(df)} rows).")
    except Exception:
        print("[INSTR][WARN] Could not save instruments CSV; continuing with in-memory list.")
    return instruments


def find_nearest_strike(instruments, spot_price):
    """Return (ce_row, pe_row) for nearest strike using instruments list."""
    if not instruments:
        return None, None
    candidates = []
    for r in instruments:
        s = r.get('strike') or r.get('strikePrice') or r.get('strike_price')
        if s is None:
            continue
        try:
            s_val = int(float(s))
            candidates.append((abs(s_val - int(spot_price)), s_val, r))
        except Exception:
            continue
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0])
    nearest_strike = candidates[0][1]
    ce = None; pe = None
    for r in instruments:
        s = r.get('strike') or r.get('strikePrice') or r.get('strike_price')
        if s is None: continue
        try:
            if int(float(s)) == nearest_strike:
                typ = (r.get('optionType') or r.get('option_type') or r.get('instrument_type') or r.get('option_type') or '').upper()
                if 'CE' in typ or 'CALL' in typ:
                    ce = r
                elif 'PE' in typ or 'PUT' in typ:
                    pe = r
        except:
            continue
    return ce, pe

# ---------------- option chain snapshot ----------------
def fetch_option_chain_snapshot():
    ts = iso()
    print(f"[{ts}] Fetching option chain snapshot (underlying={GROWW_UNDERLYING_SYMBOL}, expiry={OPTION_CHAIN_EXPIRY}) ...")
    try:
        # adjust param name if your SDK expects different field name (common pattern shown here)
        try:
            chain_resp = groww.get_option_chain(underlying=GROWW_UNDERLYING_SYMBOL, exchange=groww.EXCHANGE_NSE, expiry_date=OPTION_CHAIN_EXPIRY)
        except TypeError:
            # alternate param name
            chain_resp = groww.get_option_chain(underlying=GROWW_UNDERLYING_SYMBOL, exchange=groww.EXCHANGE_NSE, expiry=OPTION_CHAIN_EXPIRY)
    except Exception as e:
        print("[CHAIN][ERROR] Option chain SDK call failed:")
        traceback.print_exc()
        return []

    rows = []
    # common response shapes
    cand_list = None
    if isinstance(chain_resp, dict):
        cand_list = chain_resp.get('data') or chain_resp.get('records') or chain_resp.get('chain') or chain_resp.get('strikeData')
    elif isinstance(chain_resp, list):
        cand_list = chain_resp
    else:
        print("[CHAIN][WARN] Unexpected option chain response; snippet:")
        print(json.dumps(chain_resp)[:2000])
        return []

    if not cand_list:
        print("[CHAIN][WARN] Option chain returned empty list.")
        return []

    for s in cand_list:
        strike = s.get('strike') or s.get('strikePrice') or s.get('strike_price')
        ce = s.get('CE') or s.get('ce') or s.get('call') or {}
        pe = s.get('PE') or s.get('pe') or s.get('put') or {}
        rows.append({
            'timestamp': ts,
            'strike': strike,
            'ce_ltp': safe_get(ce, 'lastPrice','last_price','ltp'),
            'pe_ltp': safe_get(pe, 'lastPrice','last_price','ltp'),
            'ce_oi': safe_get(ce, 'openInterest','oi'),
            'pe_oi': safe_get(pe, 'openInterest','oi'),
            'ce_vol': safe_get(ce, 'totalTradedVolume','volume'),
            'pe_vol': safe_get(pe, 'totalTradedVolume','volume'),
            'ce_iv': safe_get(ce, 'impliedVolatility','iv'),
            'pe_iv': safe_get(pe, 'impliedVolatility','iv'),
        })
    # append to CSV (one row per strike snapshot)
    ensure_csv_header = not os.path.exists(OUT_CHAIN)
    if ensure_csv_header:
        ensure_csv_header = False
        ensure_csv_header = None
    # write
    if not os.path.exists(OUT_CHAIN):
        with open(OUT_CHAIN, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp','strike','ce_ltp','pe_ltp','ce_oi','pe_oi','ce_vol','pe_vol','ce_iv','pe_iv'])
    with open(OUT_CHAIN, "a", newline="") as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow([r['timestamp'], r['strike'], r['ce_ltp'], r['pe_ltp'], r['ce_oi'], r['pe_oi'], r['ce_vol'], r['pe_vol'], r['ce_iv'], r['pe_iv']])
    print(f"[{iso()}] Appended {len(rows)} option-strike rows to {OUT_CHAIN}")
    return rows

# ---------------- get quote ----------------
def get_quote_for_symbol(groww_symbol):
    """Return parsed LTP for a groww_symbol (e.g. 'NSE-NIFTY' or instrument trading symbol)"""
    try:
        # try common param names
        try:
            q = groww.get_quote(groww_symbol=groww_symbol, exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_CASH)
        except TypeError:
            q = groww.get_quote(groww_symbol=groww_symbol)
    except Exception:
        # fallback: some SDKs expect 'symbol' key
        try:
            q = groww.get_quote(symbol=groww_symbol)
        except Exception:
            print("[QUOTE][ERROR] get_quote failed for", groww_symbol)
            return None
    # parse LTP
    if not q:
        return None
    for key in ('lastPrice','last_price','ltp','lastTradedPrice','last_traded_price'):
        if isinstance(q, dict) and key in q and q[key] is not None:
            try:
                return float(q[key])
            except:
                pass
    # nested 'data'
    if isinstance(q, dict) and 'data' in q and isinstance(q['data'], dict):
        for key in ('lastPrice','ltp','last_traded_price','last_traded_price'):
            if key in q['data'] and q['data'][key] is not None:
                try:
                    return float(q['data'][key])
                except:
                    pass
    # couldn't parse
    print("[QUOTE][WARN] Could not parse LTP from quote response snippet:", json.dumps(q)[:200])
    return None

# ---------------- main live loop ----------------
def live_poll_loop():
    print(f"[{iso()}] Starting live polling loop (poll every {POLL_SECONDS}s, chain every {CHAIN_POLL_SECONDS}s).")
    # ensure CSV headers
    ensure_csv_header(OUT_LTP, ['timestamp','nifty_ltp','atm_ce_ltp','atm_pe_ltp'])
    if not os.path.exists(OUT_CHAIN):
        with open(OUT_CHAIN, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp','strike','ce_ltp','pe_ltp','ce_oi','pe_oi','ce_vol','pe_vol','ce_iv','pe_iv'])

    # fetch instruments once (cache)
    instruments = fetch_and_cache_instruments()

    buffer = {'nifty': None, 'atm_ce': None, 'atm_pe': None}
    last_min_written = None
    last_chain_ts = datetime.min.replace(tzinfo=TZ_LOCAL)

    try:
        while True:
            now = now_local()
            tod = now.strftime("%H:%M")
            if not TEST_MODE and (tod < MARKET_OPEN or tod > MARKET_CLOSE):
                # outside market hours — sleep a bit
                print(f"[{iso()}] Outside market hours ({tod}). Sleeping 60s.")
                time.sleep(60)
                continue

            # 1) get NIFTY quote
            nifty_ltp = get_quote_for_symbol(GROWW_UNDERLYING_SYMBOL)
            if nifty_ltp is not None:
                buffer['nifty'] = nifty_ltp

            # 2) select ATM instruments (if instruments list present)
            ce_instr = None; pe_instr = None
            if instruments and buffer.get('nifty') is not None:
                ce_instr, pe_instr = find_nearest_strike(instruments, buffer['nifty'])

            # 3) get ATM CE/PE LTP via instrument symbol if found
            if ce_instr:
                sym = ce_instr.get('tradingSymbol') or ce_instr.get('tradingsymbol') or ce_instr.get('symbol') or ce_instr.get('instrument_token')
                l = get_quote_for_symbol(sym)
                if l is not None:
                    buffer['atm_ce'] = l
            if pe_instr:
                sym = pe_instr.get('tradingSymbol') or pe_instr.get('tradingsymbol') or pe_instr.get('symbol') or pe_instr.get('instrument_token')
                l = get_quote_for_symbol(sym)
                if l is not None:
                    buffer['atm_pe'] = l

            # 4) per-minute aggregation write
            minute_now = now.replace(second=0, microsecond=0)
            if last_min_written is None or minute_now > last_min_written:
                row_ts = minute_now.isoformat()
                append_row(OUT_LTP, [row_ts, buffer.get('nifty'), buffer.get('atm_ce'), buffer.get('atm_pe')])
                print(f"[{row_ts}] WROTE LTP -> nifty:{buffer.get('nifty')} ce:{buffer.get('atm_ce')} pe:{buffer.get('atm_pe')}")
                last_min_written = minute_now

            # 5) periodic chain snapshot
            if (datetime.now(TZ_LOCAL) - last_chain_ts).total_seconds() >= CHAIN_POLL_SECONDS:
                fetch_option_chain_snapshot()
                last_chain_ts = datetime.now(TZ_LOCAL)

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped by user (KeyboardInterrupt). Exiting cleanly.")
    except Exception:
        print("Unhandled exception in main loop:")
        traceback.print_exc()

# -------------------- ENTRY POINT --------------------
def main():
    print("Groww SDK collector starting.")
    # backfill
    try:
        backfill_nifty_spot(BACKFILL_DAYS)
    except Exception as e:
        print("Backfill failed (continuing):", e)
    # start live polling
    live_poll_loop()

if __name__ == "__main__":
    main()
