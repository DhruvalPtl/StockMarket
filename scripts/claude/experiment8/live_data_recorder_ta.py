import os
import sys
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# 1. SETUP PATHS & IMPORTS
# ------------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from config import BotConfig, get_future_symbol, get_option_symbol
    # Try importing NorenApi from your local folder
    try:
        from NorenRestApiPy.NorenApi import NorenApi
    except ImportError:
        from NorenApi import NorenApi
except ImportError as e:
    print(f"❌ Setup Error: {e}")
    print("Run this script from inside your 'experiment8' folder.")
    sys.exit(1)

# 2. OUTPUT DIRECTORY
# ------------------------------------------------------------------------------
DATA_DIR = os.path.join(current_dir, 'csv')
os.makedirs(DATA_DIR, exist_ok=True)
print(f"📂 Output Folder: {DATA_DIR}")

# 3. LOGIN LOGIC (Reusing your method)
# ------------------------------------------------------------------------------
def login_and_fetch():
    # Initialize API
    api = NorenApi(host='https://piconnect.flattrade.in/PiConnectTP/', 
                   websocket='wss://piconnect.flattrade.in/PiConnectWSAPI/accv2')

    # Get Credentials from Config
    # We check common names in case you renamed them
    user_id = getattr(BotConfig, 'USER_ID', None)
    user_token = getattr(BotConfig, 'USER_TOKEN', getattr(BotConfig, 'API_KEY', None))

    if not user_id or not user_token:
        print("⚠️  Credentials missing in config.py.")
        user_id = input("Enter User ID: ")
        user_token = input("Enter User Token (API Key): ")

    print(f"🔑 Logging in as {user_id}...")
    
    # Authenticate using 'set_session' (Same as DataEngine)
    ret = api.set_session(userid=user_id, password='', usertoken=user_token)

    if ret:
        print("✅ Login Successful!")
        return api
    else:
        print("❌ Login Failed. Check your Token.")
        sys.exit(1)

def process_and_save_multiframe(res_data, base_filename, data_dir):
    """Helper to process 1-min data, resample to 5/15, calc VWAP, and save."""
    if not res_data:
        return

    df_1min = pd.DataFrame(res_data)
    
    # Standardize Time
    if 'time' in df_1min.columns:
        df_1min['time'] = pd.to_datetime(df_1min['time'], format='%d-%m-%Y %H:%M:%S')
        df_1min = df_1min.sort_values('time')
    
    # Ensure Numeric
    numeric_cols = ['into', 'inth', 'intl', 'intc', 'intv', 'intoi', 'oi']
    for col in numeric_cols:
        if col in df_1min.columns:
            df_1min[col] = pd.to_numeric(df_1min[col])

    # Loop Timeframes
    for tf in [1, 5, 15]:
        if tf == 1:
            df = df_1min.copy()
        else:
            # Resample
            agg_dict = {
                'into': 'first', 'inth': 'max', 'intl': 'min', 'intc': 'last', 'intv': 'sum'
            }
            # Add OI aggregation if present
            for oi_col in ['intoi', 'oi']:
                if oi_col in df_1min.columns:
                    agg_dict[oi_col] = 'last'
            
            # Filter agg_dict to only include columns that exist
            agg_dict = {k: v for k, v in agg_dict.items() if k in df_1min.columns}
            
            df = df_1min.set_index('time').resample(f'{tf}min').agg(agg_dict).dropna().reset_index()

        # VWAP Calculation
        required_cols = ['inth', 'intl', 'intc', 'intv']
        if all(col in df.columns for col in required_cols):
            df['tp'] = (df['inth'] + df['intl'] + df['intc']) / 3
            df['pv'] = df['tp'] * df['intv']
            df['date_temp'] = df['time'].dt.date
            df['cum_pv'] = df.groupby('date_temp')['pv'].cumsum()
            df['cum_vol'] = df.groupby('date_temp')['intv'].cumsum()
            df['vwap'] = df['cum_pv'] / df['cum_vol']
            df.drop(columns=['tp', 'pv', 'date_temp', 'cum_pv', 'cum_vol'], inplace=True)

            # --- Indicators using pandas_ta ---
            try:
                # EMA
                df['ema5'] = ta.ema(df['intc'], length=5)
                df['ema13'] = ta.ema(df['intc'], length=13)

                # RSI (14)
                df['rsi'] = ta.rsi(df['intc'], length=14)

                # ATR (14)
                df['atr'] = ta.atr(df['inth'], df['intl'], df['intc'], length=14)

                # ADX (14)
                adx_df = ta.adx(df['inth'], df['intl'], df['intc'], length=14)
                if adx_df is not None and not adx_df.empty:
                    # pandas_ta returns columns like ADX_14, DMP_14, DMN_14
                    df['adx'] = adx_df['ADX_14']
            except Exception as e:
                print(f"   ⚠️ TA Calculation Error: {e}")

        # Save
        filename = f"{base_filename}_{tf}min_{datetime.now().strftime('%Y%m%d')}.csv"
        filepath = os.path.join(data_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"   ✅ Saved: {filename} ({len(df)} rows)")

# 4. DATA FETCHING LOGIC
# ------------------------------------------------------------------------------
def fetch_and_save(api):
    # Construct Future Symbol (e.g., NIFTY29JAN26F)
    try:
        fut_sym = get_future_symbol(BotConfig.FUTURE_EXPIRY)
    except:
        fut_sym = "NIFTY27JAN26F" # Fallback if config is missing expiry
    
    print(f"📉 Target Symbol: {fut_sym}")
    
    # Search for the Token ID
    search_res = api.searchscrip(exchange='NFO', searchtext=fut_sym)
    if not search_res or 'values' not in search_res:
        print(f"❌ Could not find token for {fut_sym}")
        return
    
    token = search_res['values'][0]['token']
    tsym = search_res['values'][0]['tsym']
    print(f"   Token Found: {token} ({tsym})")

    # Fetch Futures Data (1 min only)
    print(f"⏳ Fetching 1-minute candles for {tsym}...")
    res = api.get_time_price_series(exchange='NFO', token=token, starttime=None, interval=1)
    if res:
        process_and_save_multiframe(res, tsym, DATA_DIR)
    else:
        print(f"   ⚠️ No data for {tsym}")

    # ---------------------------------------------------
    # FETCH & SAVE SPOT DATA (Nifty 50)
    # ---------------------------------------------------
    print(f"\n📉 Fetching NIFTY 50 Spot History...")
    spot_token = '26000' # Nifty 50 Token
    
    print(f"⏳ Fetching Spot 1-minute candles...")
    res = api.get_time_price_series(exchange='NSE', token=spot_token, starttime=None, interval=1)
    if res:
        process_and_save_multiframe(res, "NIFTY50_SPOT", DATA_DIR)
    else:
        print(f"   ⚠️ No Spot data")

    # Get Spot Price
    spot_res = api.get_quotes(exchange='NSE', token='26000') # Nifty 50 token
    if spot_res and 'lp' in spot_res:
        spot_price = float(spot_res['lp'])
        print(f"   ✅ Nifty 50 Spot Price: {spot_price}")
        
        # ---------------------------------------------------
        # FETCH & SAVE OPTION DATA (ATM, ATM+/-50)
        # ---------------------------------------------------
        print(f"\n📉 Fetching Option Data (Expiry: {BotConfig.OPTION_EXPIRY})...")
        
        # Calculate ATM Strike (Round to nearest 50)
        atm_strike = round(spot_price / 50) * 50
        print(f"   🎯 ATM Strike: {atm_strike}")
        
        # Define Strikes: ATM-50, ATM, ATM+50
        strikes = [atm_strike - 50, atm_strike, atm_strike + 50]
        
        for strike in strikes:
            for otype in ['CE', 'PE']:
                # Generate Symbol
                tsym = get_option_symbol(strike, otype, BotConfig.OPTION_EXPIRY)
                
                # Find Token
                search_res = api.searchscrip(exchange='NFO', searchtext=tsym)
                if search_res and 'values' in search_res:
                    # Use the first match (usually exact match)
                    token = search_res['values'][0]['token']
                    print(f"   > Fetching {tsym} (Token: {token})...")
                    
                    res = api.get_time_price_series(exchange='NFO', token=token, starttime=None, interval=1)
                    if res:
                        process_and_save_multiframe(res, tsym, DATA_DIR)
                else:
                    print(f"   ❌ Symbol not found: {tsym}")

    else:
        spot_price = 0
        print("   ❌ Could not fetch Spot Price")

if __name__ == "__main__":
    api_instance = login_and_fetch()
    fetch_and_save(api_instance)
    print("\n🏁 Done. Check the 'csv' folder.")
