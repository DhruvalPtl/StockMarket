import time
import math
from growwapi import GrowwAPI

class GrowwDataEngine:
    def __init__(self, api_key, api_secret, expiry_date):
        print("🔌 CONNECTING TO GROWW (Premium Data Mode)...")
        self.api = GrowwAPI(api_key, api_secret)
        self.expiry = expiry_date
        
        # Data Containers
        self.spot_ltp = 0
        self.prev_spot = 0 # For Velocity calculation
        self.atm_ce = {'symbol': '', 'ltp': 0, 'delta': 0.5} 
        self.atm_pe = {'symbol': '', 'ltp': 0, 'delta': -0.5}
        
    def update(self):
        try:
            # 1. Get Nifty Spot Price
            # Note: "NSE_NIFTY" is the typical symbol, check your specific symbol mapping
            quote = self.api.get_live_data("NSE_NIFTY50") 
            self.prev_spot = self.spot_ltp
            self.spot_ltp = quote['ltp']

            # 2. Find ATM Strike
            strike = round(self.spot_ltp / 50) * 50
            
            # 3. Get Option Chain (WITH REAL GREEKS)
            # This call fetches the full chain for that expiry
            chain = self.api.get_option_chain("NIFTY", self.expiry)
            
            # 4. Extract Data for ATM Strike
            # Groww Structure: chain['strikes'][str(strike)]['CE']['greeks']
            strike_data = chain['strikes'].get(str(strike))
            
            if strike_data:
                # Call Data
                ce = strike_data['CE']
                self.atm_ce['ltp'] = ce['ltp']
                self.atm_ce['symbol'] = ce['trading_symbol']
                self.atm_ce['delta'] = ce['greeks']['delta'] # <--- REAL DELTA!
                
                # Put Data
                pe = strike_data['PE']
                self.atm_pe['ltp'] = pe['ltp']
                self.atm_pe['symbol'] = pe['trading_symbol']
                self.atm_pe['delta'] = pe['greeks']['delta'] # <--- REAL DELTA!
                
        except Exception as e:
            print(f"⚠️ Data Error: {e}")