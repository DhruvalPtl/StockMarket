import csv
import time
from pathlib import Path
import pandas as pd
from datetime import timedelta
from growwapi import GrowwAPI

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM1Njg0NzYsImlhdCI6MTc2NTE2ODQ3NiwibmJmIjoxNzY1MTY4NDc2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJhMTg3NDVhMy1hN2M1LTRlOTQtODE1MS1lZjUxZDQ5OGE2Y2RcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjBlOWMyYWZmLTM0NzktNDUyMi1iODE4LTczNTZlMzFkYmY1Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjNkMWQ6MWZmMDo1YWFjOjYwNTYsMTcyLjcxLjE5OC4xOSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1MzU2ODQ3NjQzNn0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.VuAMgqoC3e32gduObByNz97jFfG-ikXoREum26XPkvyMpj9JgCedXBI81jxGTPTrZD9i1wIL0s38LPd9vc9ApA"
API_SECRET = "xy0sbQ4r*!HN3&&UKc9vpwti4xx8PR)("

def auth():
    try:
        token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
        return GrowwAPI(token)
    except Exception as e:
        print(f"Auth failed: {e}")
        exit()

groww = auth()
print("Logged into Groww!")

g = groww

df = g.get_all_instruments()    # expects DataFrame

# quick inspect (optional)
print("Instruments shape:", df.shape)
print("Columns:", df.columns.tolist())

# 2) normalize column names to lower-case for safe access
df.columns = [c.lower() for c in df.columns]

# 3) choose filter conditions
# - underlying_symbol equals 'NIFTY' OR trading_symbol contains 'NIFTY'
# - instrument_type indicates CE or PE
conds = (
    (df.get('underlying_symbol', '').astype(str).str.upper() == 'NIFTY') |
    (df.get('trading_symbol', '').astype(str).str.upper().str.contains('NIFTY'))
)
opt_type_col = df.get('instrument_type', 'instrument_type')
conds = conds & (df[opt_type_col].astype(str).str.upper().isin(['CE','PE','OPTCE','OPTPE','OPTION']))

# also ensure this is in derivatives segment if available
if 'segment' in df.columns:
    conds = conds & (df['segment'].astype(str).str.upper().str.contains('FNO|FO|F&O|FUT|DER', na=False) == False).replace({True: True, False: True})
    # note: some vendors use different segment names — we will not strictly filter segment to avoid false negatives

# 4) apply filter
opts = df[conds].copy()

# 5) normalize expiry_date to ISO YYYY-MM-DD
# expiry might look like '12/29/2026' or '2026-12-29' etc.
if 'expiry_date' in opts.columns:
    opts['expiry_iso'] = pd.to_datetime(opts['expiry_date'], errors='coerce').dt.strftime('%Y-%m-%d')
else:
    opts['expiry_iso'] = None

# 6) select useful columns (keep safe fallbacks)
cols = []
for c in ['trading_symbol','groww_symbol','internal_trading_symbol','name','expiry_iso','expiry_date','strike_price','instrument_type','lot_size','tick_size','exchange','segment']:
    if c in opts.columns:
        cols.append(c)

out = opts[cols].drop_duplicates().sort_values(['expiry_iso','strike_price','trading_symbol'])

# 7) save CSV
out_path = Path("nifty_option_symbols_from_instruments.csv")
out.to_csv(out_path, index=False)

print("Found", len(out), "option rows. Saved to", out_path)
print(out.head(10).to_string(index=False))