"""
FLATTRADE SYMBOL SEARCH DEBUG TOOL
===================================
Interactive tool to test symbol searches.

Usage:
    python debug_search_symbols.py
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig
from utils.flattrade_wrapper import FlattradeWrapper


def search_symbol(api, exchange, search_text):
    """Search for a symbol"""
    print(f"\n🔍 Searching {exchange} for: '{search_text}'")
    print("-" * 60)
    
    try:
        res = api.api.searchscrip(exchange=exchange, searchtext=search_text)
        
        if res and 'values' in res:
            print(f"✅ Found {len(res['values'])} results:\n")
            print(f"{'Token':<10} {'Symbol':<30} {'Description':<30}")
            print("-" * 70)
            
            for item in res['values'][:10]:  # Show first 10
                token = item.get('token', '')
                symbol = item.get('tsym', '')
                desc = item.get('instname', '')
                print(f"{token:<10} {symbol:<30} {desc:<30}")
                
            return res['values']
        else:
            print("❌ No results found")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def main():
    print("\n" + "="*70)
    print("🔍 FLATTRADE SYMBOL SEARCH DEBUG TOOL")
    print("="*70)
    
    # Connect
    print("\n📡 Connecting to Flattrade...")
    api = FlattradeWrapper(
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN
    )
    
    if not api.is_connected:
        print("❌ Connection failed")
        return
    
    print("✅ Connected!\n")
    
    
    # Interactive mode
    print("\n" + "="*70)
    print("🎮 INTERACTIVE MODE")
    print("="*70)
    print("Enter 'quit' to exit\n")
    
    while True:
        print("\n" + "-"*30)
        search_text = input("Enter symbol (e.g. 'NIFTY 24000 CE', 'RELIANCE', 'quit'): ").strip()
        
        if search_text.lower() in ['quit', 'exit']:
            break
            
        if not search_text:
            continue
            
        # Auto-detect exchange: Options/Futures are usually in NFO
        exchange = 'NSE'
        if any(x in search_text.upper() for x in [' CE', ' PE', 'FUT', 'NIFTY', 'BANKNIFTY']):
             if any(c.isdigit() for c in search_text):
                 exchange = 'NFO'
        
        print(f"Searching in Exchange: {exchange}")
        search_symbol(api, exchange, search_text)


if __name__ == "__main__":
    main()
