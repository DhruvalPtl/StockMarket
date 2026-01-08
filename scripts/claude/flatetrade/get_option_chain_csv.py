"""
Get Option Chain Data and Save to CSV
Usage: python get_option_chain_csv.py
"""
import sys
import os
import pandas as pd
from datetime import datetime
from config import BotConfig
from utils.NorenRestApiPy.NorenApi import NorenApi

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


from utils.flattrade_wrapper import FlattradeWrapper

def main():
    print("="*60)
    print("📊 FLATTRADE OPTION CHAIN DOWNLOADER")
    print("="*60)

    # 1. Connect to API
    print("\n1️⃣ Connecting to Flattrade...")
    try:
        api = FlattradeWrapper(
            user_id=BotConfig.USER_ID,
            user_token=BotConfig.USER_TOKEN
        )
        
        if not api.is_connected:
            print("❌ Connection Failed. Check token in config.py")
            return
        print("✅ Connected successfully")
        
    except Exception as e:
        print(f"❌ Error connecting: {e}")
        return

    # 2. Get Spot Price (for reference)
    print("\n2️⃣ Fetching NIFTY Spot Price...")
    spot_price = 0
    try:
        quote = api.get_quote("NSE-NIFTY")
        if quote and 'last_price' in quote:
            spot_price = quote['last_price']
            print(f"   NIFTY Spot: ₹{spot_price:.2f}")
        else:
            print("⚠️ Could not fetch spot price, using default 24000")
            spot_price = 24000
    except Exception as e:
        print(f"⚠️ Error fetching spot: {e}")
        spot_price = 24000

    # 3. Fetch Option Chain
    expiry = BotConfig.OPTION_EXPIRY
    print(f"\n3️⃣ Fetching Option Chain for Expiry: {expiry}")
    
    try:
        # Fetch using wrapper (Handles symbol formatting automatically)
        chain_data = api.get_option_chain(
            exchange="NFO",
            underlying="NIFTY",
            expiry=expiry
        )

        if chain_data and 'strikes' in chain_data and len(chain_data['strikes']) > 0:
            strikes = chain_data['strikes']
            print(f"✅ Received {len(strikes)} strikes")

            # 4. Convert to DataFrame
            rows = []
            for strike, data in strikes.items():
                row = {'strike': float(strike)}
                
                # CE Data
                if 'CE' in data:
                    ce = data['CE']
                    row['ce_symbol'] = ce.get('symbol', '')
                    row['ce_ltp'] = ce.get('ltp', 0)
                    row['ce_oi'] = ce.get('oi', 0)
                    row['ce_volume'] = ce.get('volume', 0)
                else:
                    row['ce_symbol'] = ''
                    row['ce_ltp'] = 0
                    row['ce_oi'] = 0
                    row['ce_volume'] = 0
                    
                # PE Data
                if 'PE' in data:
                    pe = data['PE']
                    row['pe_symbol'] = pe.get('symbol', '')
                    row['pe_ltp'] = pe.get('ltp', 0)
                    row['pe_oi'] = pe.get('oi', 0)
                    row['pe_volume'] = pe.get('volume', 0)
                else:
                    row['pe_symbol'] = ''
                    row['pe_ltp'] = 0
                    row['pe_oi'] = 0
                    row['pe_volume'] = 0
                    
                rows.append(row)
            
            df = pd.DataFrame(rows)
            df = df.sort_values('strike')
            
            # 5. Save to CSV
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"option_chain_{expiry}_{timestamp_str}.csv"
            filepath = os.path.join(current_dir, filename)
            df.to_csv(filepath, index=False)
            
            print(f"\n✅ Saved to: {filepath}")
            
            # Show ATM view
            atm_strike = round(spot_price / 50) * 50
            print(f"\n📊 ATM View ({atm_strike}):")
            atm_df = df[(df['strike'] >= atm_strike - 100) & (df['strike'] <= atm_strike + 100)]
            print(atm_df[['strike', 'ce_ltp', 'ce_oi', 'pe_ltp', 'pe_oi']].to_string(index=False))
            
            # Calculate PCR
            total_ce_oi = df['ce_oi'].sum()
            total_pe_oi = df['pe_oi'].sum()
            pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
            print(f"\n📈 PCR: {pcr:.2f} (CE OI: {total_ce_oi}, PE OI: {total_pe_oi})")

        else:
            print("❌ No option chain data received")
            print(f"   Check if Expiry '{expiry}' matches the search results (e.g., 13JAN26 -> 2026-01-13).")
            print(f"   Try running 'debug_search_symbols.py' to verify.")

    except Exception as e:
        print(f"❌ Error fetching option chain: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()