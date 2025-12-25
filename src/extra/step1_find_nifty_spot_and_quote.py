# step1_find_nifty_spot_and_quote.py
import pandas as pd, json, sys, traceback
from growwapi import GrowwAPI

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
INSTR_CSV = "groww_instruments.csv"
SEARCH = "NIFTY"

# auth
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    try:
        groww = GrowwAPI(API_KEY)
    except Exception as e:
        print("AUTH ERROR", e); sys.exit(1)

df = pd.read_csv(INSTR_CSV, dtype=str)

# Filter: rows that reference NIFTY and have no strike_price and no expiry_date (likely spot/index)
candidates = df[
    df.apply(lambda r:
        ("NIFTY" in str(r.get('trading_symbol','')).upper() or
         "NIFTY" in str(r.get('groww_symbol','')).upper() or
         "NIFTY" in str(r.get('underlying_symbol','')).upper())
        and (pd.isna(r.get('strike_price')) or str(r.get('strike_price')).strip() == "") 
        and (pd.isna(r.get('expiry_date')) or str(r.get('expiry_date')).strip() == ""), axis=1)
]

print("Found", len(candidates), "spot-like NIFTY candidates. Showing up to 20:")
print(candidates.head(20)[['trading_symbol','groww_symbol','underlying_symbol','segment','exchange','expiry_date','strike_price']].to_dict(orient='records'))

if len(candidates)==0:
    print("No obvious spot rows (no strike/expiry). Trying broader search (including rows where strike is empty OR expiry empty).")
    broad = df[df.apply(lambda r: ("NIFTY" in str(r.get('trading_symbol','')).upper() or "NIFTY" in str(r.get('groww_symbol','')).upper() or "NIFTY" in str(r.get('underlying_symbol','')).upper()) and (pd.isna(r.get('strike_price')) or pd.isna(r.get('expiry_date'))), axis=1)]
    print("Broad found", len(broad))
    print(broad.head(20)[['trading_symbol','groww_symbol','underlying_symbol','segment','exchange','expiry_date','strike_price']].to_dict(orient='records'))
    sys.exit(0)

# Try get_quote on first few candidates with CASH and FNO segments (whichever fits)
def try_quote(sym, seg_const_name):
    try:
        seg_const = getattr(groww, seg_const_name)
        resp = groww.get_quote(sym, groww.EXCHANGE_NSE, seg_const)
        print(f"get_quote success for {sym} with {seg_const_name} ->", json.dumps(resp, default=str)[:1000])
    except Exception as e:
        print(f"get_quote failed for {sym} with {seg_const_name} ->", type(e).__name__, str(e)[:300])

for i, row in candidates.head(6).iterrows():
    sym = row.get('trading_symbol') or row.get('internal_trading_symbol') or row.get('groww_symbol')
    print("\nTRYING:", sym, "segment field:", row.get('segment'))
    # try CASH then FNO (spot typically CASH)
    if hasattr(groww, "SEGMENT_CASH"):
        try_quote(sym, "SEGMENT_CASH")
    if hasattr(groww, "SEGMENT_FNO"):
        try_quote(sym, "SEGMENT_FNO")

print("\nDone.")
