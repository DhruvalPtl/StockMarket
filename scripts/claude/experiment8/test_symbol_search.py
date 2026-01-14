"""
Symbol Search Test - Find correct Flattrade symbols for NIFTY trading

This script helps identify the exact symbol names and tokens needed for:
- NIFTY 50 Index
- NIFTY Futures (current month)
- NIFTY Options

Run this to find the correct symbols before running the main bot.
"""

import sys
import os

# Add pythonAPI-main to path
current_dir = os.path.dirname(os.path.abspath(__file__))
claude_dir = os.path.dirname(current_dir)
flattrade_api_path = os.path.join(claude_dir, 'pythonAPI-main')
flattrade_dist_path = os.path.join(flattrade_api_path, 'dist')
sys.path.insert(0, flattrade_api_path)
sys.path.insert(0, flattrade_dist_path)

from api_helper import NorenApiPy
from datetime import datetime

# Load credentials from config
sys.path.insert(0, current_dir)
from config import BotConfig


def search_and_display(api, exchange, search_text, description):
    """Search for a symbol and display results."""
    print(f"\n{'='*80}")
    print(f"🔍 Searching: {description}")
    print(f"   Exchange: {exchange}")
    print(f"   Search Text: '{search_text}'")
    print(f"{'='*80}")
    
    try:
        result = api.searchscrip(exchange=exchange, searchtext=search_text)
        
        if not result:
            print("❌ No results returned (None)")
            return None
            
        if 'stat' in result and result['stat'] != 'Ok':
            print(f"❌ Search failed: {result}")
            return None
        
        if 'values' not in result:
            print(f"❌ No 'values' in result: {result}")
            return None
        
        values = result['values']
        print(f"\n✅ Found {len(values)} results:\n")
        
        for i, item in enumerate(values[:10], 1):  # Show first 10
            tsym = item.get('tsym', 'N/A')
            token = item.get('token', 'N/A')
            exch = item.get('exch', 'N/A')
            instname = item.get('instname', 'N/A')
            
            print(f"   {i}. {tsym}")
            print(f"      Token: {token} | Exchange: {exch} | Instrument: {instname}")
            
            # Show additional fields if available
            if 'pp' in item:
                print(f"      Price: {item['pp']}")
            if 'ls' in item:
                print(f"      Lot Size: {item['ls']}")
            print()
        
        if len(values) > 10:
            print(f"   ... and {len(values) - 10} more results\n")
        
        return values
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║           FLATTRADE SYMBOL SEARCH TEST                           ║
    ║           Find correct symbols for NIFTY trading                 ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Connect to API
    print("\n🔑 Connecting to Flattrade API...")
    try:
        api = NorenApiPy()
        ret = api.set_session(
            userid=BotConfig.USER_ID,
            password='',
            usertoken=BotConfig.USER_TOKEN
        )
        
        if ret:
            print("✅ Connected successfully!\n")
        else:
            print("❌ Connection failed!")
            return
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    # ========== TEST 1: NIFTY 50 INDEX ==========
    searches = [
        ("NSE", "NIFTY", "NIFTY 50 Index - Search 'NIFTY'"),
        ("NSE", "Nifty 50", "NIFTY 50 Index - Search 'Nifty 50'"),
        ("NSE", "NIFTY 50", "NIFTY 50 Index - Search 'NIFTY 50'"),
        ("NSE", "26000", "NSE Index Token (26000 is common for NIFTY)"),
    ]
    
    for exchange, search_text, description in searches:
        search_and_display(api, exchange, search_text, description)
    
    # ========== TEST 2: NIFTY FUTURES ==========
    # Try different date formats
    expiry_dt = datetime.strptime(BotConfig.FUTURE_EXPIRY, "%Y-%m-%d")
    
    future_searches = [
        ("NFO", "NIFTY", "NIFTY Futures - Generic search"),
        ("NFO", f"NIFTY{expiry_dt.strftime('%d%b%y').upper()}FUT", f"NIFTY Futures - Format: NIFTY{expiry_dt.strftime('%d%b%y').upper()}FUT"),
        ("NFO", f"NIFTY {expiry_dt.strftime('%d%b%y').upper()} FUT", f"NIFTY Futures - With spaces"),
        ("NFO", "NIFTYFUT", "NIFTY Futures - Search 'NIFTYFUT'"),
    ]
    
    for exchange, search_text, description in future_searches:
        search_and_display(api, exchange, search_text, description)
    
    # ========== TEST 3: NIFTY OPTIONS ==========
    option_expiry_dt = datetime.strptime(BotConfig.OPTION_EXPIRY, "%Y-%m-%d")
    
    option_searches = [
        ("NFO", f"NIFTY{option_expiry_dt.strftime('%d%b%y').upper()}", f"NIFTY Options - Date: {option_expiry_dt.strftime('%d%b%y').upper()}"),
        ("NFO", f"NIFTY {option_expiry_dt.strftime('%d%b%y').upper()}", f"NIFTY Options - With space"),
        ("NFO", "NIFTY 24000 CE", "NIFTY Options - Specific strike example"),
    ]
    
    for exchange, search_text, description in option_searches:
        search_and_display(api, exchange, search_text, description)
    
    # ========== SUMMARY ==========
    print("\n" + "="*80)
    print("📝 SUMMARY & RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the search results above, update your config/code with the correct symbols:

1. NIFTY 50 INDEX (NSE):
   - Look for the result with token and exact symbol name
   - Common symbol: Usually listed as "Nifty 50" or similar
   
2. NIFTY FUTURE (NFO):
   - Check the format: NIFTYXXMMMYYFUT (e.g., NIFTY27JAN26FUT)
   - Or: NIFTY XXMMMYY FUT with spaces
   
3. NIFTY OPTIONS (NFO):
   - Format: NIFTYXXMMMYY#####CE/PE
   - Example: NIFTY13JAN2624000CE
   
💡 TIP: Use the exact 'tsym' value from the search results in your code
💡 TIP: Cache the 'token' values to avoid repeated searches
    """)
    
    print("\n✅ Symbol search test complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
