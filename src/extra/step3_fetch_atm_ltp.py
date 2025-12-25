# step3_fetch_atm_ltp.py
import csv, json
from datetime import datetime
from dateutil import tz
from growwapi import GrowwAPI

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"

# ATM trading symbols discovered earlier
NIFTY_SYMBOL = "NIFTY"
ATM_CE = "NIFTY2610626200CE"
ATM_PE = "NIFTY2610626200PE"

OUT_CSV = "option_ltp_1m.csv"
TZ = tz.gettz("Asia/Kolkata")

def now_iso():
    return datetime.now(TZ).replace(microsecond=0).isoformat()

# auth
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    groww = GrowwAPI(API_KEY)

def parse_ltp(q):
    if not q:
        return None
    # common fields
    for k in ("last_price","lastPrice","ltp","lastTradedPrice","last_traded_price","last_price"):
        if isinstance(q, dict) and k in q and q[k] not in (None,""):
            try:
                return float(q[k])
            except:
                pass
    # nested data
    if isinstance(q, dict) and "data" in q and isinstance(q["data"], dict):
        for k in ("lastPrice","ltp"):
            if k in q["data"] and q["data"][k] not in (None,""):
                try: return float(q["data"][k])
                except: pass
    # fallback: find first numeric leaf
    def find_num(x):
        if isinstance(x, (int,float)): return float(x)
        if isinstance(x, dict):
            for v in x.values():
                r = find_num(v)
                if r is not None: return r
        return None
    return find_num(q)

# ensure CSV header exists
try:
    with open(OUT_CSV, "r", newline="") as f:
        has = f.read(1)
except FileNotFoundError:
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp","nifty_ltp","atm_ce_ltp","atm_pe_ltp"])

# 1) get nifty spot
try:
    qn = groww.get_quote(NIFTY_SYMBOL, groww.EXCHANGE_NSE, groww.SEGMENT_CASH)
    nifty_ltp = parse_ltp(qn)
except Exception as e:
    print("NIFTY get_quote failed:", type(e).__name__, str(e))
    print("Raw exception; aborting.")
    raise

print("NIFTY quote raw (trim):", json.dumps(qn, default=str)[:800])
print("Parsed nifty_ltp:", nifty_ltp)

# 2) get ATM CE / PE
try:
    qce = groww.get_quote(ATM_CE, groww.EXCHANGE_NSE, groww.SEGMENT_FNO)
    qpe = groww.get_quote(ATM_PE, groww.EXCHANGE_NSE, groww.SEGMENT_FNO)
    atm_ce_ltp = parse_ltp(qce)
    atm_pe_ltp = parse_ltp(qpe)
except Exception as e:
    print("ATM option get_quote failed:", type(e).__name__, str(e))
    print("CE raw (trim):", json.dumps(qce, default=str)[:800] if 'qce' in locals() else None)
    print("PE raw (trim):", json.dumps(qpe, default=str)[:800] if 'qpe' in locals() else None)
    raise

print("Parsed atm_ce_ltp:", atm_ce_ltp, "atm_pe_ltp:", atm_pe_ltp)

# 3) append to CSV
ts = now_iso()
with open(OUT_CSV, "a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([ts, nifty_ltp, atm_ce_ltp, atm_pe_ltp])

print("Wrote row to", OUT_CSV)
