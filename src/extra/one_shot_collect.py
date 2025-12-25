
# one_shot_collect_fixed.py
# Robust one-shot to write one row to option_ltp_1m.csv and one snapshot to option_chain_1m.csv
# - tries multiple get_quote signatures
# - picks nearest expiry from groww_instruments.csv if needed for option chain

import os, csv, json, traceback
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd
from growwapi import GrowwAPI

# ---------------- CONFIG ----------------
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"

OUT_LTP = "option_ltp_1m.csv"
OUT_CHAIN = "option_chain_1m.csv"
INSTR_CSV = "groww_instruments.csv"
UNDERLYING_SYMBOL = "NSE-NIFTY"   # keep same format as used earlier
# If you want to force an expiry (YYYY-MM-DD) set here; otherwise script will auto-select nearest expiry
FORCE_EXPIRY = None

TZ_LOCAL = tz.gettz("Asia/Kolkata")

def now_iso():
    return datetime.now(TZ_LOCAL).replace(microsecond=0).isoformat()

def ensure_header(path, header):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(header)

# ---------------- auth ----------------
groww = None
try:
    access_token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(access_token)
except Exception:
    try:
        # fallback: instantiate with token-like key (some SDKs accept)
        groww = GrowwAPI(API_KEY)
    except Exception:
        print("Auth failed — adapt this block to match your working auth flow.")
        raise

# ---------------- load instruments ----------------
if not os.path.exists(INSTR_CSV):
    raise SystemExit(f"Missing {INSTR_CSV}. Run your collector to generate it or export instruments CSV from Groww.")

df_ins = pd.read_csv(INSTR_CSV, low_memory=False)
instruments = df_ins.to_dict(orient='records')
print(f"Loaded instruments: {len(instruments)} rows.")

# ---------------- helpers ----------------
def try_get_quote_with_various_params(symbol_candidate):
    """
    Try several calling patterns for groww.get_quote until one returns a non-empty response.
    Returns the raw response or None.
    """
    attempts = [
        ({"symbol": symbol_candidate}, "symbol"),
        ({"groww_symbol": symbol_candidate}, "groww_symbol"),
        ({"groww_symbol": symbol_candidate, "exchange": getattr(groww, "EXCHANGE_NSE", None)}, "groww_symbol+exchange"),
        ({"trading_symbol": symbol_candidate}, "trading_symbol"),
        ({"instrument_token": symbol_candidate}, "instrument_token"),
        ({}, "no-args")  # fallback to bare call if SDK uses internal defaults
    ]
    for kwargs, label in attempts:
        try:
            # remove None values from kwargs
            kk = {k:v for k,v in kwargs.items() if v is not None}
            if kk:
                resp = groww.get_quote(**kk)
            else:
                # try calling with positional single arg (some SDKs expect a single param)
                try:
                    resp = groww.get_quote(symbol_candidate)
                except TypeError:
                    resp = groww.get_quote()
            print(f"[QUOTE] Tried get_quote with {label}, got type {type(resp)}")
            if resp:
                return resp, label
        except TypeError as te:
            # signature mismatch; try next
            #print("TypeError for get_quote with", label, te)
            continue
        except Exception as e:
            # Some SDKs wrap errors; print short form and continue
            print(f"[QUOTE] get_quote attempt {label} raised {type(e).__name__}: {str(e)[:200]}")
            continue
    return None, None

def parse_ltp_from_quote(q):
    if not q:
        return None
    # common direct fields
    for key in ('lastPrice','last_price','ltp','lastTradedPrice','last_traded_price'):
        if isinstance(q, dict) and key in q and q[key] not in (None, ''):
            try:
                return float(q[key])
            except:
                pass
    # nested under 'data'
    if isinstance(q, dict) and 'data' in q and isinstance(q['data'], dict):
        for key in ('lastPrice','ltp','last_price'):
            if key in q['data'] and q['data'][key] not in (None,''):
                try:
                    return float(q['data'][key])
                except:
                    pass
    # sometimes the SDK returns {"price": {...}} or custom
    # try to find any numeric value in the dict as a fallback
    def find_numeric(d):
        if isinstance(d, (int,float)):
            return float(d)
        if isinstance(d, dict):
            for v in d.values():
                res = find_numeric(v)
                if res is not None:
                    return res
        return None
    res = find_numeric(q)
    return res

def find_nearest_atm_symbols_from_instruments(instruments, spot_price):
    """
    From instruments list (rows) find nearest strike and return trading_symbol for CE and PE.
    Handles common column name variants.
    """
    candidates = []
    for r in instruments:
        s = r.get('strike') or r.get('strikePrice') or r.get('strike_price') or r.get('strike_price_instrument')
        if s is None:
            continue
        try:
            s_val = int(float(s))
            candidates.append((abs(s_val - int(spot_price)), s_val))
        except:
            continue
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x[0])
    nearest_strike = candidates[0][1]
    # Determine expiry for that strike
    ce_sym = None; pe_sym = None; expiry = None
    for r in instruments:
        try:
            s = r.get('strike') or r.get('strikePrice') or r.get('strike_price')
            if s is None: continue
            if int(float(s)) != nearest_strike: continue
            typ = (r.get('optionType') or r.get('option_type') or r.get('instrument_type') or r.get('segment') or '').upper()
            # trading symbol field variations:
            sym = r.get('tradingsymbol') or r.get('trading_symbol') or r.get('symbol') or r.get('internal_trading_symbol') or r.get('instrument_token')
            # expiry field variations
            expiry_field = r.get('expiry') or r.get('expiryDate') or r.get('expiry_date') or r.get('expiry_dt') or r.get('expiry_date_instrument')
            if expiry is None and expiry_field:
                # normalize date
                try:
                    # some expiry strings are like '26DEC2025' - try many formats
                    # prefer ISO-like dates if available
                    expiry = str(expiry_field)
                except:
                    expiry = str(expiry_field)
            if 'CE' in typ or 'CALL' in typ:
                ce_sym = sym or ce_sym
            if 'PE' in typ or 'PUT' in typ:
                pe_sym = sym or pe_sym
        except Exception as e:
            print("instruments fetch failed with exception:")
            traceback.print_exc()
    return ce_sym, pe_sym, expiry

def choose_nearest_expiry_from_instruments(instruments, underlying_filter=None):
    """
    Inspect instruments list and return the nearest expiry string in YYYY-MM-DD if possible.
    Looks for fields named 'expiry', 'expiryDate', 'expiry_date', and normalizes them.
    """
    exps = set()
    for r in instruments:
        v = r.get('expiry') or r.get('expiryDate') or r.get('expiry_date') or r.get('expiry_dt')
        if v is None:
            # sometimes expiry is part of trading symbol; skip for now
            continue
        vs = str(v)
        # try to parse to date
        try:
            # if format already YYYY-MM-DD or similar, parse with pandas then format
            dt = pd.to_datetime(vs, errors='coerce')
            if not pd.isna(dt):
                exps.add(dt.date())
        except:
            continue
    if not exps:
        return None
    today = datetime.now(tz=TZ_LOCAL).date()
    future_exps = sorted([d for d in exps if d >= today])
    if not future_exps:
        return None
    nearest = future_exps[0]
    return nearest.isoformat()

# ---------------- Step 1: Get NIFTY quote ----------------
print("Fetching NIFTY quote (trying multiple signatures)...")
quote_resp, used_label = try_get_quote_with_various_params(UNDERLYING_SYMBOL)
nifty_ltp = parse_ltp_from_quote(quote_resp) if quote_resp else None
print("NIFTY quote attempt label:", used_label, "parsed LTP:", nifty_ltp)
if nifty_ltp is None:
    # try to fetch via instrument token lookup in instruments (some APIs require exchange_token)
    # find an instrument row for underlying to get exchange_token/instrument_token
    underlying_row = None
    for r in instruments:
        # match fields that contain underlying symbol
        # many trading symbols include underlying in uppercase (e.g. 'NIFTY26DEC...')
        if (str(r.get('trading_symbol') or r.get('tradingsymbol') or r.get('symbol') or '').upper().startswith('NIFTY')) or (r.get('exchange') and r.get('exchange').upper()=='NSE' and 'NIFTY' in str(r.get('trading_symbol') or '').upper()):
            underlying_row = r
            break
    if underlying_row:
        tok = underlying_row.get('exchange_token') or underlying_row.get('instrument_token') or underlying_row.get('instrumentToken')
        if tok:
            print("Attempting get_quote with instrument_token:", tok)
            try:
                q2 = groww.get_quote(instrument_token=tok)
                nifty_ltp = parse_ltp_from_quote(q2)
            except Exception as e:
                print("instrument_token get_quote attempt failed:", type(e).__name__, str(e)[:200])
print("Final nifty_ltp:", nifty_ltp)

# ---------------- Step 2: select ATM CE/PE trading symbols ----------------
atm_ce_sym, atm_pe_sym, atm_expiry_from_strike = None, None, None
if nifty_ltp is not None:
    atm_ce_sym, atm_pe_sym, atm_expiry_from_strike = find_nearest_atm_symbols_from_instruments(instruments, nifty_ltp)
    print("Found ATM symbols:", atm_ce_sym, atm_pe_sym, "expiry_from_strike:", atm_expiry_from_strike)
else:
    print("No nifty LTP available; cannot select ATM strikes reliably.")

# ---------------- Step 3: fetch LTPs for ATM CE/PE if available ----------------
atm_ce_ltp = None; atm_pe_ltp = None
if atm_ce_sym:
    q_ce, lab = try_get_quote_with_various_params(atm_ce_sym)
    atm_ce_ltp = parse_ltp_from_quote(q_ce) if q_ce else None
    print(f"CE quote tried with {lab}, ltp={atm_ce_ltp}")
if atm_pe_sym:
    q_pe, lab = try_get_quote_with_various_params(atm_pe_sym)
    atm_pe_ltp = parse_ltp_from_quote(q_pe) if q_pe else None
    print(f"PE quote tried with {lab}, ltp={atm_pe_ltp}")

# write one LTP row (timestamp, nifty, ce, pe)
ensure_header(OUT_LTP, ['timestamp','nifty_ltp','atm_ce_ltp','atm_pe_ltp'])
with open(OUT_LTP, "a", newline="") as f:
    csv.writer(f).writerow([now_iso(), nifty_ltp, atm_ce_ltp, atm_pe_ltp])
print("Appended to", OUT_LTP)

# ---------------- Step 4: fetch option chain snapshot for expiry ----------------
expiry_to_use = FORCE_EXPIRY
if expiry_to_use is None:
    expiry_to_use = choose_nearest_expiry_from_instruments(instruments)
    # if still none, try expiry found earlier from ATM strike rows
    if expiry_to_use is None and atm_expiry_from_strike:
        try:
            # try parse atm_expiry_from_strike to ISO if possible
            dt = pd.to_datetime(str(atm_expiry_from_strike), errors='coerce')
            if not pd.isna(dt):
                expiry_to_use = dt.date().isoformat()
            else:
                expiry_to_use = atm_expiry_from_strike
        except:
            expiry_to_use = atm_expiry_from_strike

print("Expiry selected for option chain:", expiry_to_use)
if not expiry_to_use:
    print("No expiry could be selected. To fetch option chain you must provide expiry_date. Set FORCE_EXPIRY to YYYY-MM-DD in the script or supply instruments CSV with expiry field.")
else:
    try:
        # try multiple signatures
        chain = None
        try:
            chain = groww.get_option_chain(underlying=UNDERLYING_SYMBOL, exchange=groww.EXCHANGE_NSE, expiry_date=expiry_to_use)
        except TypeError:
            try:
                chain = groww.get_option_chain(underlying=UNDERLYING_SYMBOL, exchange=groww.EXCHANGE_NSE, expiry=expiry_to_use)
            except TypeError:
                chain = groww.get_option_chain(underlying=UNDERLYING_SYMBOL, expiry_date=expiry_to_use)
        # normalize cand list
        cand = None
        if isinstance(chain, dict):
            cand = chain.get('data') or chain.get('records') or chain.get('chain') or chain.get('strikeData')
        elif isinstance(chain, list):
            cand = chain
        if not cand:
            print("Option-chain call returned no strikes or in unexpected format. Dumping snippet:")
            print(json.dumps(chain)[:2000])
        else:
            ensure_header(OUT_CHAIN, ['timestamp','strike','ce_ltp','pe_ltp','ce_oi','pe_oi','ce_vol','pe_vol','ce_iv','pe_iv'])
            ts = now_iso()
            rows = []
            for s in cand:
                strike = s.get('strike') or s.get('strikePrice') or s.get('strike_price')
                ce = s.get('CE') or s.get('ce') or s.get('call') or {}
                pe = s.get('PE') or s.get('pe') or s.get('put') or {}
                rows.append([ts, strike,
                             ce.get('lastPrice') or ce.get('ltp'),
                             pe.get('lastPrice') or pe.get('ltp'),
                             ce.get('openInterest') or ce.get('oi'),
                             pe.get('openInterest') or pe.get('oi'),
                             ce.get('totalTradedVolume') or ce.get('volume'),
                             pe.get('totalTradedVolume') or pe.get('volume'),
                             ce.get('impliedVolatility') or None,
                             pe.get('impliedVolatility') or None])
            # append to CSV
            with open(OUT_CHAIN, "a", newline="") as f:
                writer = csv.writer(f)
                for r in rows:
                    writer.writerow(r)
            print(f"Wrote {len(rows)} strike rows to {OUT_CHAIN}")
    except Exception as e:
        print("Option-chain fetch failed with exception:")
        traceback.print_exc()

print("one_shot_collect_fixed.py finished.")
