"""
Get Index List and Nifty Futures from Flattrade
Usage: python get_nifty_futures.py
"""
import sys
import os
import pandas as pd

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig
from utils.api_helper import NorenApiPy

def main():
    print("="*60)
    print("🔍 FLATTRADE INDEX & FUTURES FETCHER")
    print("="*60)

    # 1. Connect to API
    print("\n1️⃣ Connecting to Flattrade...")
    try:
        api = NorenApiPy()
        ret = api.set_session(
            userid=BotConfig.USER_ID, 
            password='', 
            usertoken=BotConfig.USER_TOKEN
        )
        
        if not ret:
            print("❌ Connection Failed. Check token in config.py")
            return
        print("✅ Connected successfully")
        
    except Exception as e:
        print(f"❌ Error connecting: {e}")
        return

    # 2. Get Index Spot Prices
    print("\n2️⃣ Major Indices (Spot):")
    print("-" * 40)
    indices = [
        {'name': 'NIFTY 50', 'token': '26000', 'exch': 'NSE'},
        {'name': 'NIFTY BANK', 'token': '26009', 'exch': 'NSE'},
        {'name': 'FINNIFTY', 'token': '26037', 'exch': 'NSE'}
    ]
    
    for idx in indices:
        try:
            q = api.get_quotes(exchange=idx['exch'], token=idx['token'])
            if q and 'lp' in q:
                print(f"{idx['name']:<15} : ₹{q['lp']}")
            else:
                print(f"{idx['name']:<15} : N/A")
        except Exception as e:
            print(f"{idx['name']:<15} : Error")

    # 3. Search for NIFTY Futures
    print("\n3️⃣ NIFTY Futures (NFO):")
    print("-" * 80)
    print(f"{'Token':<10} | {'Symbol':<25} | {'Expiry':<15} | {'LTP':<10}")
    print("-" * 80)
    
    try:
        # Search for "NIFTY FUT" in NFO exchange
        res = api.searchscrip(exchange='NFO', searchtext='NIFTY FUT')
        
        if res and 'values' in res:
            futures = res['values']
            # Sort by symbol to likely get near month first
            futures.sort(key=lambda x: x.get('tsym', ''))
            
            for fut in futures:
                token = fut.get('token')
                tsym = fut.get('tsym')
                dname = fut.get('dname', '') # Display name usually contains expiry
                
                # Get Live Price
                ltp = "-"
                q = api.get_quotes(exchange='NFO', token=token)
                if q and 'lp' in q:
                    ltp = f"₹{q['lp']}"
                
                print(f"{token:<10} | {tsym:<25} | {dname:<15} | {ltp:<10}")
        else:
            print("❌ No futures found matching 'NIFTY FUT'")
            
    except Exception as e:
        print(f"❌ Error searching futures: {e}")

    print("\n" + "="*60)

if __name__ == "__main__":
    main()
