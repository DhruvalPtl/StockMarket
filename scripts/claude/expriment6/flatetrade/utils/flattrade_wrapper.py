import logging
import pandas as pd
from datetime import datetime
import time

# Use the NorenApi you already have working
from utils.NorenRestApiPy.NorenApi import NorenApi

class FlattradeWrapper:
    def __init__(self, user_id, user_token):
        # 1. Initialize API
        self.api = NorenApi(
            host='https://piconnect.flattrade.in/PiConnectTP', 
            websocket='wss://piconnect.flattrade.in/PiConnectWSTp'
        )
        
        # 2. Set Session (The method you proved works)
        print(f"🔗 Connecting with Token: {user_token[:10]}...")
        ret = self.api.set_session(userid=user_id, password='', usertoken=user_token)

        if ret:
            print("✅ Flattrade Wrapper Connected Successfully!")
            self.is_connected = True
        else:
            print("❌ Connection Failed. Token might be expired.")
            self.is_connected = False

    def get_historical_candles(self, exchange, segment, symbol, start_time, end_time, interval):
        """
        Translates Flattrade data to the format your bot needs.
        """
        try:
            # 1. Map Timeframe
            # Groww uses '1minute', Flattrade uses '1'
            tf_map = {'1minute': '1', '3minute': '3', '5minute': '5', '15minute': '15'}
            tf = tf_map.get(interval, '1')
            
            # 2. Get Token (CRITICAL STEP)
            # We must find the numeric 'token' (e.g., 26000 for Nifty)
            token = self._get_token(symbol, exchange)
            if not token:
                print(f"⚠️ Token not found for {symbol}")
                return {'candles': []}

            # 3. Convert Time to Epoch (Seconds)
            # start_time comes as "2025-01-05 09:15:00"
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            start_epoch = str(int(start_dt.timestamp()))
            
            # 4. Fetch Data
            # Note: Flattrade returns: time, into (open), inth (high), intl (low), intc (close)
            ret = self.api.get_time_price_series(exchange=exchange, token=token, starttime=start_epoch, interval=tf)
            
            if not ret:
                return {'candles': []}
                
            # 5. Convert to List of Dicts (Groww Format)
            candles = []
            for c in ret:
                # Flattrade time format: "05-01-2026 09:15:00"
                c_time_str = c.get('time')
                c_dt = datetime.strptime(c_time_str, "%d-%m-%Y %H:%M:%S")
                
                candles.append({
                    't': c_dt,
                    'o': float(c.get('into')),
                    'h': float(c.get('inth')),
                    'l': float(c.get('intl')),
                    'c': float(c.get('intc')),
                    'v': int(c.get('intv', 0))
                })
                
            # Sort just in case
            candles.sort(key=lambda x: x['t'])
            return {'candles': candles}

        except Exception as e:
            print(f"❌ Data Fetch Error: {e}")
            return {'candles': []}

    def _get_token(self, symbol, exchange):
        """Helper to find the numeric token for a symbol"""
        # 1. Handle NIFTY SPOT
        if symbol == "NSE-NIFTY" or symbol == "NIFTY":
            return "26000"  # Nifty 50 Token
            
        # 2. Handle NIFTY FUTURES (e.g., NSE-NIFTY-27Jan26-FUT)
        if "FUT" in symbol:
            try:
                parts = symbol.split('-')  # ['NSE', 'NIFTY', '27Jan26', 'FUT']
                date_part = parts[2]  # '27Jan26'
                
                # Convert '27Jan26' to '27JAN' for search
                # Extract day and month
                import re
                match = re.match(r'(\d{1,2})([A-Za-z]{3})', date_part)
                if match:
                    day = match.group(1).zfill(2)
                    month = match.group(2).upper()
                    search_str = f"NIFTY {day}{month} FUT"
                    
                    print(f"🔍 Searching Flattrade for: {search_str}")
                    res = self.api.searchscrip(exchange=exchange, searchtext=search_str)
                    
                    if res and 'values' in res and len(res['values']) > 0:
                        token = res['values'][0]['token']
                        print(f"✅ Found token: {token} for {symbol}")
                        return token
                    else:
                        print(f"❌ No results for {search_str}")
            except Exception as e:
                print(f"❌ Token search error: {e}")
                
        return None

    def get_quote(self, symbol):
        # Quick Quote for Nifty
        if symbol == "NSE-NIFTY":
            res = self.api.get_quotes(exchange='NSE', token='26000')
            if res and 'lp' in res:
                return {'last_price': float(res['lp'])}
        return {'last_price': 0.0}

    def get_option_chain(self, exchange, underlying, expiry):
        """
        Fetch option chain from Flattrade.
        Returns data in Groww-compatible format.
        """
        try:
            # Convert expiry format: "2026-01-06" -> "06JAN26"
            from datetime import datetime
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
            expiry_str = expiry_dt.strftime("%d%b%y").upper()
            
            # Flattrade option chain format
            ret = self.api.get_option_chain(
                exchange=exchange,
                tradingsymbol=f"NIFTY{expiry_str}",
                strikePrice="",
                count="20"
            )
            
            if not ret or 'values' not in ret:
                return {'strikes': {}}
            
            # Convert to Groww format
            strikes = {}
            for opt in ret['values']:
                strike = opt.get('strprc', 0)
                opt_type = opt.get('optt', '')  # 'CE' or 'PE'
                
                if strike not in strikes:
                    strikes[strike] = {}
                
                strikes[strike][opt_type] = {
                    'symbol': opt.get('tsym', ''),
                    'ltp': float(opt.get('lp', 0)),
                    'oi': int(opt.get('oi', 0)),
                    'volume': int(opt.get('v', 0)),
                    'token': opt.get('token', '')
                }
            
            return {'strikes': strikes}
            
        except Exception as e:
            print(f"❌ Option chain error: {e}")
            return {'strikes': {}}