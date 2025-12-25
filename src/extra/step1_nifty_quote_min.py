# step1_nifty_quote_positional.py
from growwapi import GrowwAPI
import json, sys, traceback

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
UNDERLYING = "NSE-NIFTY"

# auth
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    try:
        groww = GrowwAPI(API_KEY)
    except Exception as e:
        print("AUTH ERROR:", e); sys.exit(1)

def print_try(desc, resp):
    print("=== TRY:", desc, "===\nType:", type(resp))
    try:
        print(json.dumps(resp, default=str)[:4000])
    except Exception:
        print(str(resp))

def parse_ltp(q):
    if not q: return None
    for k in ("lastPrice","last_price","ltp","lastTradedPrice","last_traded_price"):
        if isinstance(q, dict) and k in q and q[k] not in (None,""):
            try: return float(q[k])
            except: pass
    if isinstance(q, dict) and "data" in q and isinstance(q["data"], dict):
        for k in ("lastPrice","ltp","last_price"):
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

# Try positional calls with expected args
trials = [
    ("trading_symbol, exchange, segment",
     lambda: groww.get_quote(UNDERLYING, groww.EXCHANGE_NSE, groww.SEGMENT_CASH)),
    ("trading_symbol, segment, exchange",
     lambda: groww.get_quote(UNDERLYING, groww.SEGMENT_CASH, groww.EXCHANGE_NSE)),
    ("exchange, segment, trading_symbol",
     lambda: groww.get_quote(groww.EXCHANGE_NSE, groww.SEGMENT_CASH, UNDERLYING)),
    ("use underlying's instrument_token if present",
     lambda: groww.get_quote(UNDERLYING)),  # fallback
]

success = False
for desc, fn in trials:
    try:
        resp = fn()
        print_try(desc, resp)
        ltp = parse_ltp(resp)
        print("Parsed LTP:", ltp)
        success = True
        break
    except TypeError as te:
        print("TypeError for", desc, "->", te)
    except Exception as e:
        print("Exception for", desc, "->", type(e).__name__, str(e)[:500])
        traceback.print_exc()

if not success:
    print("\nAll positional attempts failed. Print SDK clues:")
    print("dir(groww) snippet:")
    print([m for m in dir(groww) if any(k in m.lower() for k in ('quote','get_quote','trading','exchange','segment'))])
    # show signature if possible
    try:
        import inspect
        print("Signature of get_quote:", inspect.signature(groww.get_quote))
    except Exception as e:
        print("Could not get signature:", e)
