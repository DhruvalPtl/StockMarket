# collect_atm_ltp.py
import csv, json
from datetime import datetime
from dateutil import tz
import pandas as pd
from growwapi import GrowwAPI

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM1Njg0NzYsImlhdCI6MTc2NTE2ODQ3NiwibmJmIjoxNzY1MTY4NDc2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhMTg3NDVhMy1hN2M1LTRlOTQtODE1MS1lZjUxZDQ5OGE2Y2RcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjBlOWMyYWZmLTM0NzktNDUyMi1iODE4LTczNTZlMzFkYmY1Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjNkMWQ6MWZmMDo1YWFjOjYwNTYsMTcyLjcxLjE5OC4xOSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1MzU2ODQ3NjQzNn0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.VuAMgqoC3e32gduObByNz97jFfG-ikXoREum26XPkvyMpj9JgCedXBI81jxGTPTrZD9i1wIL0s38LPd9vc9ApA"
API_SECRET = "xy0sbQ4r*!HN3&&UKc9vpwti4xx8PR)("
TZ = tz.gettz("Asia/Kolkata")

OUT = "option_ltp_1m.csv"
INSTR = "groww_instruments.csv"

def now_iso():
    return datetime.now(TZ).replace(microsecond=0).isoformat()

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception:
        return GrowwAPI(API_KEY)

groww = auth()

# helper parse
def parse_ltp(q):
    if not q: return None
    for k in ("last_price","lastPrice","ltp","lastTradedPrice"):
        if isinstance(q, dict) and k in q and q[k] not in (None,""):
            try: return float(q[k])
            except: pass
    if isinstance(q, dict) and "data" in q and isinstance(q["data"], dict):
        for k in ("lastPrice","ltp"):
            if k in q["data"] and q["data"][k] not in (None,""):
                try: return float(q["data"][k])
                except: pass
    def find_num(x):
        if isinstance(x,(int,float)): return float(x)
        if isinstance(x,dict):
            for v in x.values():
                r = find_num(v)
                if r is not None: return r
        return None
    return find_num(q)

# 1) get NIFTY spot
q_n = groww.get_quote("NIFTY", groww.EXCHANGE_NSE, groww.SEGMENT_CASH)
nifty_ltp = parse_ltp(q_n)
print("NIFTY LTP:", nifty_ltp)

# 2) find ATM strike from instruments CSV
df = pd.read_csv(INSTR, dtype=str)
df['strike_num'] = df['strike_price'].apply(lambda x: float(x) if pd.notna(x) and str(x).strip()!="" else None)
def is_nifty_row(r):
    ts = str(r.get('trading_symbol','')).upper()
    us = str(r.get('underlying_symbol','')).upper() if pd.notna(r.get('underlying_symbol')) else ''
    return ("NIFTY" in ts or "NIFTY" in us) and ("BANK" not in ts) and ("FIN" not in ts)
cand = df[df.apply(is_nifty_row, axis=1)].copy()
cand = cand[(cand['segment'].str.upper()=='FNO') & cand['strike_num'].notna()]
cand['diff'] = cand['strike_num'].apply(lambda s: abs(s - nifty_ltp))
nearest = float(cand.sort_values('diff').iloc[0]['strike_num'])
subset = cand[cand['strike_num']==nearest]
ce_row = subset[subset['instrument_type'].str.upper().str.contains('CE', na=False)]
pe_row = subset[subset['instrument_type'].str.upper().str.contains('PE', na=False)]
atm_ce = ce_row.iloc[0]['trading_symbol'] if not ce_row.empty else None
atm_pe = pe_row.iloc[0]['trading_symbol'] if not pe_row.empty else None
print("Nearest strike:", nearest, "ATM CE:", atm_ce, "ATM PE:", atm_pe)

# 3) get CE/PE quotes
qce = groww.get_quote(atm_ce, groww.EXCHANGE_NSE, groww.SEGMENT_FNO)
qpe = groww.get_quote(atm_pe, groww.EXCHANGE_NSE, groww.SEGMENT_FNO)
ce_ltp = parse_ltp(qce)
pe_ltp = parse_ltp(qpe)
print("Parsed atm_ce_ltp:", ce_ltp, "atm_pe_ltp:", pe_ltp)

# ensure CSV header exists
try:
    with open(OUT, "r") as f: pass
except FileNotFoundError:
    with open(OUT, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp","nifty_ltp","atm_ce_ltp","atm_pe_ltp"])

# append
with open(OUT, "a", newline="") as f:
    csv.writer(f).writerow([now_iso(), nifty_ltp, ce_ltp, pe_ltp])
print("Appended to", OUT)
