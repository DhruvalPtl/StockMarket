# step1_find_trading_symbol_and_quote.py
import pandas as pd, json, sys, traceback
from growwapi import GrowwAPI
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
INSTR_CSV = "groww_instruments.csv"
SEARCH_TERM = "NIFTY"

# auth
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    try:
        groww = GrowwAPI(API_KEY)
    except Exception as e:
        print("AUTH ERROR", e); sys.exit(1)

# load instruments
df = pd.read_csv(INSTR_CSV, dtype=str)
cols = df.columns.tolist()
print("Instrument columns:", cols)

# find candidate rows (search multiple columns for 'NIFTY')
candidates = df[
    df.apply(lambda r: any((str(r.get(c, "")).upper().find(SEARCH_TERM) != -1) for c in ['trading_symbol','tradingsymbol','trading_symbol','symbol','internal_trading_symbol','instrument_name','name'] if c in r.index), axis=1)
]

print(f"Found {len(candidates)} candidate rows containing '{SEARCH_TERM}'. Showing up to 20:")
print(candidates.head(20).to_dict(orient='records'))

# pick first candidate trading symbol (if any)
if len(candidates) == 0:
    print("No candidates found for NIFTY in instruments CSV. Paste head of CSV if you think this is wrong.")
    sys.exit(0)

# choose a likely trading symbol:
row = candidates.iloc[0]
# common column names for trading symbol
tr_sym = None
for col in ('trading_symbol','tradingsymbol','symbol','internal_trading_symbol','internal_tradingsymbol'):
    if col in row.index and pd.notna(row[col]) and str(row[col]).strip() != "":
        tr_sym = str(row[col]).strip()
        break

print("Selected candidate trading_symbol:", tr_sym)
print("Row snippet:", {c: row.get(c) for c in ['exchange','exchange_token','segment','expiry','strike','instrument_token'] if c in row.index})

# Try get_quote with segment guesses (FNO then CASH)
def try_quote_with(trading_symbol, exchange_const, segment_const):
    try:
        resp = groww.get_quote(trading_symbol, exchange_const, segment_const)
        print("=== get_quote success with", exchange_const, segment_const, "===\n", json.dumps(resp, default=str)[:2000])
        # parse LTP quickly
        def parse_ltp(q):
            if not q: return None
            for k in ("lastPrice","last_price","ltp","lastTradedPrice","last_traded_price"):
                if isinstance(q, dict) and k in q and q[k] not in (None,""):
                    try: return float(q[k])
                    except: pass
            if isinstance(q, dict) and "data" in q and isinstance(q["data"], dict):
                for k in ("lastPrice","ltp"):
                    if k in q["data"] and q["data"][k] not in (None,""):
                        try: return float(q["data"][k])
                        except: pass
            # fallback: search nested numeric
            def find_num(x):
                if isinstance(x,(int,float)): return float(x)
                if isinstance(x,dict):
                    for v in x.values():
                        r = find_num(v)
                        if r is not None: return r
                return None
            return find_num(q)
        print("Parsed LTP:", parse_ltp(resp))
        return True
    except Exception as e:
        print("get_quote failed for", exchange_const, segment_const, "->", type(e).__name__, str(e)[:300])
        return False

# try likely segments/exchanges
tried = False
for seg in (getattr(groww, "SEGMENT_FNO", None), getattr(groww, "SEGMENT_CASH", None), getattr(groww, "SEGMENT_CURRENCY", None)):
    if seg is None: continue
    ex = getattr(groww, "EXCHANGE_NSE", None)
    if ex is None: continue
    print("Attempting get_quote with exchange:", ex, "segment:", seg, "trading_symbol:", tr_sym)
    ok = try_quote_with(tr_sym, ex, seg)
    tried = True
    if ok:
        break

if not tried:
    print("Could not form exchange/segment constants from SDK.")
