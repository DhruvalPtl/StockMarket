"""
SYMBOL FINDER
Helper script to search for valid trading symbols and tokens in Flattrade.
Saves results to 'found_symbols.csv'.

Usage:
    python find_symbols.py
"""

import sys
import os
import csv

# ==============================================================================
# CONFIGURATION
# ==============================================================================
try:
    from config import BotConfig
    USER_ID = BotConfig.USER_ID
    USER_TOKEN = BotConfig.USER_TOKEN
    print("✅ Loaded credentials from config.py")
except ImportError:
    print("⚠️ config.py not found, using hardcoded credentials")
    USER_ID = "FZ31397"
    USER_TOKEN = "67e59eb37f6931699cbc5bf2b20e67403572120341624b0de47e7147119298ae"
# ==============================================================================

# Setup Path for API
current_dir = os.path.dirname(os.path.abspath(__file__))
api_path = os.path.join(current_dir, 'pythonAPI-main')
if os.path.exists(api_path):
    sys.path.append(api_path)

# Import API
try:
    from NorenApi import NorenApi
except ImportError:
    try:
        from api_helper import NorenApi
    except ImportError:
        print("❌ Error: Could not import NorenApi.")
        print("Ensure 'pythonAPI-main' folder is present or NorenApi.py is in the script directory.")
        sys.exit(1)

def find_symbols():
    print("\n" + "="*60)
    print("🔎 FLATTRADE SYMBOL FINDER")
    print("="*60)

    # 1. Connect
    api = NorenApi(host='https://piconnect.flattrade.in/PiConnectTP/', 
                   websocket='wss://piconnect.flattrade.in/PiConnectWSAPI/accv2')
    
    print("1. Connecting to API...")
    ret = api.set_session(userid=USER_ID, password='', usertoken=USER_TOKEN)
    
    if not ret:
        print("❌ Login failed. Please check your USER_TOKEN.")
        return

    print(f"✅ Connected as {USER_ID}")

    # 2. Search (Modified to find Spot and Derivatives)
    all_symbols = []
    queries = [
        ("NSE", "Nifty"),  # Spot Index
        ("NFO", "NIFTY")      # Futures & Options
    ]

    print("2. Searching for symbols...")
    for exch, text in queries:
        print(f"   > Searching for '{text}' in {exch}...")
        res = api.searchscrip(exchange=exch, searchtext=text)
        if res and 'values' in res:
            print(f"     Found {len(res['values'])} symbols.")
            all_symbols.extend(res['values'])
        else:
            print(f"     No symbols found for {text} in {exch}.")

    if not all_symbols:
        print("❌ No symbols found or API error.")
        return

    # 3. Save to CSV
    output_file = os.path.join(current_dir, 'found_symbols.csv')
    print(f"3. Saving to {output_file}...")
    
    futures_found = []
    spot_found = []
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write Header
        writer.writerow(['Exchange', 'Token', 'Symbol', 'Instrument', 'OptionType', 'LotSize'])
        
        for s in all_symbols:
            exch = s.get('exch')
            token = s.get('token')
            tsym = s.get('tsym')
            inst = s.get('instname', '') # FUTIDX, OPTIDX
            optt = s.get('optt', '')
            ls = s.get('ls', '')
            
            writer.writerow([exch, token, tsym, inst, optt, ls])
            
            # Collect Spot
            if exch == 'NSE':
                spot_found.append(f"{tsym} (Token: {token})")
            
            # Collect Futures for display
            if inst == 'FUTIDX' or (inst == '' and tsym.endswith('F')):
                futures_found.append(f"{tsym} (Token: {token})")

    print("\n📋 SPOT INDICES FOUND:")
    print("-" * 40)
    if not spot_found:
        print("   (No Spot symbols found)")
    for s in sorted(spot_found):
        print(f"   {s}")

    print("\n📋 FUTURES FOUND:")
    print("-" * 40)
    if not futures_found:
        print("   (No FUTIDX symbols found in search results)")
    for f in sorted(futures_found):
        print(f"   {f}")
    print("-" * 40)
    print(f"\n✅ Done. Open 'found_symbols.csv' to see all Options & Futures.")

if __name__ == "__main__":
    find_symbols()
