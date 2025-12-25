# step4_fetch_option_chain_fixed.py
import csv, json
from datetime import datetime
from dateutil import tz
import pandas as pd
from growwapi import GrowwAPI
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTM0ODUwMTcsImlhdCI6MTc2NTA4NTAxNywibmJmIjoxNzY1MDg1MDE3LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJmYjg0YzJmOS04NGUwLTQ2NGMtYWFkZC0wZjMyZTBiNDZmY2FcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjVlZDUwZmU2LTBiNjktNDBlMC04ZDJmLTJlZjE3Y2YxZDYwN1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjFjNDg6YTliYjo5MTZiOmI4NWQsMTcyLjcxLjE5OC4xMjgsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTM0ODUwMTc4ODR9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.GCoXAEdA0BkhB88lQmsYqzl96qaGudoM3UvzHxEh_tGfODPmrLzTNPMo8KCeTpzwf46Hp-wU41QxjNPwGyHmag"
API_SECRET = "F@ldixy2hTCYKBq30fyNIyz#PaJ1Ui9i"
INSTR_CSV = "groww_instruments.csv"
OUT_CHAIN = "option_chain_1m.csv"
UNDERLYING = "NIFTY"
TZ = tz.gettz("Asia/Kolkata")

def now_iso():
    return datetime.now(TZ).replace(microsecond=0).isoformat()

# auth
try:
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    groww = GrowwAPI(token)
except Exception:
    groww = GrowwAPI(API_KEY)

# pick expiry from instruments (nearest future)
df = pd.read_csv(INSTR_CSV, dtype=str)
df['expiry_dt'] = pd.to_datetime(df.get('expiry_date', pd.Series([None]*len(df))), errors='coerce')
today = pd.Timestamp.now().normalize()
future = df[df['expiry_dt'].notna() & (df['expiry_dt'] >= today)]
expiry_to_use = None
if not future.empty:
    expiry_to_use = future['expiry_dt'].min().date().isoformat()
else:
    # fallback: try to use earliest non-null expiry
    all_exp = df['expiry_date'].dropna().unique()
    expiry_to_use = all_exp[0] if len(all_exp)>0 else None

if expiry_to_use is None:
    raise SystemExit("No expiry discovered in instruments CSV. Inspect groww_instruments.csv.")
print("Using expiry:", expiry_to_use)

# call option chain
try:
    chain = groww.get_option_chain(underlying=UNDERLYING, exchange=groww.EXCHANGE_NSE, expiry_date=expiry_to_use)
except TypeError:
    chain = groww.get_option_chain(underlying=UNDERLYING, expiry_date=expiry_to_use)
except Exception as e:
    print("option_chain call failed:", type(e).__name__, str(e))
    raise

# Normalize strikes extraction
strikes_data = None
if isinstance(chain, dict):
    if 'strikes' in chain and isinstance(chain['strikes'], dict):
        # SDK returns mapping strike-> {CE:..., PE:...}
        strikes_data = []
        for strike_str, d in chain['strikes'].items():
            try:
                strike_num = float(strike_str)
            except:
                # if keys are not numeric, try inner fields
                strike_num = d.get('strike') or d.get('strike_price') or None
                try:
                    strike_num = float(strike_num) if strike_num is not None else None
                except:
                    strike_num = None
            strikes_data.append({'strike': strike_num, 'CE': d.get('CE', {}), 'PE': d.get('PE', {})})
    else:
        # older shapes: look for 'data' or 'records' or top-level list
        if 'data' in chain and isinstance(chain['data'], list):
            strikes_data = chain['data']
        elif 'records' in chain and isinstance(chain['records'], list):
            strikes_data = chain['records']
        elif isinstance(chain.get('strikes'), list):
            strikes_data = chain.get('strikes')
        else:
            # last fallback: maybe chain already in list form
            if isinstance(chain, list):
                strikes_data = chain

if not strikes_data:
    print("Option-chain format unexpected; dumping JSON (trim):")
    print(json.dumps(chain, default=str)[:4000])
    raise SystemExit("No strikes parsed from option_chain response.")

# Ensure CSV header exists
try:
    with open(OUT_CHAIN, "r", newline="") as f:
        _ = f.read(1)
except FileNotFoundError:
    with open(OUT_CHAIN, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp","strike","ce_ltp","pe_ltp","ce_oi","pe_oi","ce_vol","pe_vol","ce_iv","pe_iv"])

# helper to extract fields safely
def gv(d, keys):
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None

rows_written = 0
ts = now_iso()
sample_rows = []
with open(OUT_CHAIN, "a", newline="") as f:
    writer = csv.writer(f)
    for item in strikes_data:
        # item can be dict with 'strike' or {'strike':..., 'CE':..., 'PE':...}
        if isinstance(item, dict) and 'strike' in item and (item.get('CE') is not None or item.get('PE') is not None):
            strike = item.get('strike')
            ce = item.get('CE') or {}
            pe = item.get('PE') or {}
        else:
            # item is probably in older format where item itself contains strike and CE/PE fields directly
            strike = gv(item, ['strike','strike_price','strikePrice'])
            ce = item.get('CE') or item.get('ce') or {}
            pe = item.get('PE') or item.get('pe') or {}

        # Common possible places for fields:
        ce_ltp = gv(ce, ['ltp','lastPrice','last_price'])
        pe_ltp = gv(pe, ['ltp','lastPrice','last_price'])
        ce_oi  = gv(ce, ['open_interest','openInterest','oi'])
        pe_oi  = gv(pe, ['open_interest','openInterest','oi'])
        ce_vol = gv(ce, ['volume','totalTradedVolume','total_traded_volume'])
        pe_vol = gv(pe, ['volume','totalTradedVolume','total_traded_volume'])
        # IV may be present directly or inside greeks.iv
        ce_iv  = gv(ce, ['impliedVolatility','iv','implied_volatility']) or (ce.get('greeks') and gv(ce.get('greeks'), ['iv','impliedVolatility']))
        pe_iv  = gv(pe, ['impliedVolatility','iv','implied_volatility']) or (pe.get('greeks') and gv(pe.get('greeks'), ['iv','impliedVolatility']))

        # write only if strike exists
        if strike is None:
            continue

        writer.writerow([ts, strike, ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol, ce_iv, pe_iv])
        rows_written += 1
        if len(sample_rows) < 8:
            sample_rows.append([ts, strike, ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol, ce_iv, pe_iv])

print("Wrote", rows_written, "strike rows to", OUT_CHAIN)
print("Sample rows written (up to 8):")
for r in sample_rows:
    print(r)
