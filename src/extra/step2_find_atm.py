# step2_find_atm.py
import math, json, pandas as pd
from growwapi import GrowwAPI

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
INSTR_CSV = "groww_instruments.csv"
# ------- auth (same pattern you used already) -------
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    groww = GrowwAPI(API_KEY)

# 1) get NIFTY LTP
q = groww.get_quote("NIFTY", groww.EXCHANGE_NSE, groww.SEGMENT_CASH)
# defensive parse for numeric LTP
def parse_ltp(q):
    if not q: return None
    for k in ("last_price","lastPrice","last_price","ltp","lastTradedPrice"):
        if isinstance(q, dict) and k in q and q[k] not in (None,""):
            try: return float(q[k])
            except: pass
    # nested 'data' fallback
    if isinstance(q, dict) and "data" in q and isinstance(q["data"], dict):
        for k in ("lastPrice","ltp"):
            if k in q["data"] and q["data"][k] not in (None,""):
                try: return float(q["data"][k])
                except: pass
    return None

nifty_ltp = parse_ltp(q)
print("NIFTY LTP:", nifty_ltp)
if nifty_ltp is None:
    raise SystemExit("Failed to parse nifty ltp from quote: " + json.dumps(q)[:1000])

# 2) read instruments and find nearest strike for NIFTY options (segment FNO)
df = pd.read_csv(INSTR_CSV, dtype=str)

# convert strike_price to numeric where present
df['strike_num'] = df['strike_price'].apply(lambda x: float(x) if pd.notna(x) and str(x).strip()!="" else None)

# Filter NIFTY option rows (underlying_symbol may be 'NIFTY' or trading_symbol contains 'NIFTY' but exclude BANKNIFTY/FINNIFTY)
def is_nifty_row(r):
    ts = str(r.get('trading_symbol','')).upper()
    us = str(r.get('underlying_symbol','')).upper() if pd.notna(r.get('underlying_symbol')) else ''
    return ("NIFTY" in ts or "NIFTY" in us) and ("BANK" not in ts) and ("FIN" not in ts)

cand = df[df.apply(is_nifty_row, axis=1)].copy()
# keep only FNO (options) rows with strike
cand = cand[(cand['segment'].str.upper()=='FNO') & cand['strike_num'].notna()]

if cand.empty:
    raise SystemExit("No NIFTY option rows (FNO+strike) found in instruments CSV.")

# find nearest strike (round to nearest existing strike grid)
cand['diff'] = cand['strike_num'].apply(lambda s: abs(s - nifty_ltp))
# determine unique strikes and pick nearest unique strike
nearest_strike = sorted(cand[['strike_num','diff']].drop_duplicates().values.tolist(), key=lambda x:x[1])[0][0]
nearest_strike = float(nearest_strike)
print("Nearest strike chosen:", nearest_strike)

# choose CE and PE trading symbols for that strike and nearest expiry (prefer nearest expiry >= today)
# convert expiry_date to datetime
cand['expiry_dt'] = pd.to_datetime(cand['expiry_date'], errors='coerce')
today = pd.Timestamp.now(tz=None).normalize()
future_cand = cand[cand['expiry_dt'].notna() & (cand['expiry_dt'] >= today)]
if not future_cand.empty:
    # choose nearest expiry
    nearest_expiry = future_cand['expiry_dt'].min()
    subset = future_cand[future_cand['strike_num']==nearest_strike]
else:
    subset = cand[cand['strike_num']==nearest_strike]

# find CE and PE rows
ce_row = subset[subset['instrument_type'].str.upper().str.contains('CE', na=False)]
pe_row = subset[subset['instrument_type'].str.upper().str.contains('PE', na=False)]

atm_ce = ce_row.iloc[0]['trading_symbol'] if not ce_row.empty else None
atm_pe = pe_row.iloc[0]['trading_symbol'] if not pe_row.empty else None
expiry = (subset.iloc[0]['expiry_date'] if not subset.empty else None)

print("ATM CE trading_symbol:", atm_ce)
print("ATM PE trading_symbol:", atm_pe)
print("Expiry for these strikes:", expiry)
