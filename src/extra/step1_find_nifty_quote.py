# step1_find_nifty_quote.py
import pandas as pd, json, sys, traceback
from growwapi import GrowwAPI

API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
INSTR_CSV = "groww_instruments.csv"
SEARCH_TERM = "NIFTY"   # will exclude BANKNIFTY explicitly

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
# keep rows that mention NIFTY but exclude BANKNIFTY
candidates = df[df.apply(lambda r: ("NIFTY" in str(r.get('trading_symbol','')).upper() or "NIFTY" in str(r.get('groww_symbol','')).upper() or "NIFTY" in str(r.get('underlying_symbol','')).upper()) and ("BANK" not in str(r.get('trading_symbol','')).upper()), axis=1)]

print("Found", len(candidates), "NIFTY-related candidate rows (excluding BANKNIFTY). Showing up to 20:")
print(candidates.head(20)[['trading_symbol','groww_symbol','underlying_symbol','segment','expiry_date','strike_price']].to_dict(orient='records'))

if len(candidates) == 0:
    print("No NIFTY rows found. Paste a small head of groww_instruments.csv and I'll inspect.")
    sys.exit(0)

# pick first candidate (you can change index if you want)
row = candidates.iloc[0]
tr_sym = row.get('trading_symbol') or row.get('internal_trading_symbol') or row.get('groww_symbol')
print("Selected trading_symbol:", tr_sym, "segment:", row.get('segment'))

# try get_quote with FNO then CASH
def try_quote(trading_symbol, seg):
    try:
        resp = groww.get_quote(trading_symbol, groww.EXCHANGE_NSE, getattr(groww, seg))
        print("=== get_quote success for", trading_symbol, seg, "===\n", json.dumps(resp, default=str)[:2000])
    except Exception as e:
        print("get_quote failed for", trading_symbol, seg, "->", type(e).__name__, str(e)[:400])

# attempt FNO (most index options are FNO)
if hasattr(groww, "SEGMENT_FNO"):
    try_quote(tr_sym, "SEGMENT_FNO")
# attempt CASH if FNO did not work
if hasattr(groww, "SEGMENT_CASH"):
    try_quote(tr_sym, "SEGMENT_CASH")

print("Done.")
