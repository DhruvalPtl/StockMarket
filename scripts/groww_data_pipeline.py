import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta
import sys
import os

class GrowwDataEngine:
    def __init__(self, api_key, api_secret, expiry_date, fut_symbol):
        print(f"\n⚙️ STARTING ENGINE | Expiry: {expiry_date} | Future: {fut_symbol}")
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.expiry_date = expiry_date # YYYY-MM-DD
        self.fut_symbol = fut_symbol
        
        # 1. SETUP DATE FORMATS
        try:
            self.dt = datetime.strptime(expiry_date, "%Y-%m-%d")
            self.sym_date = self.dt.strftime("%d%b%y").upper() # 23DEC25
        except ValueError:
            print("❌ CRITICAL: Expiry must be YYYY-MM-DD"); sys.exit()

        # 2. INIT PUBLIC VARIABLES (The "Clean Data")
        self.timestamp = None
        self.spot_ltp = 0.0
        self.fut_ltp = 0.0
        self.rsi = 0.0
        self.ema5 = 0.0
        self.ema13 = 0.0
        self.vwap = 0.0
        self.atm_strike = 0
        self.pcr = 0.0
        
        # ATM Option Data Containers
        self.atm_ce = {'symbol': '', 'ltp': 0, 'oi': 0, 'delta': 0, 'theta': 0}
        self.atm_pe = {'symbol': '', 'ltp': 0, 'oi': 0, 'delta': 0, 'theta': 0}

        # 3. SETUP AUTO-LOGGING
        self.log_file = f"D:\\StockMarket\\StockMarket\\scripts\\engine_log\\Engine_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv()
        
        # 4. CONNECT
        self._connect()

    def _connect(self):
        try:
            token = GrowwAPI.get_access_token(api_key=self.api_key, secret=self.api_secret)
            self.groww = GrowwAPI(token)
            print("✅ Engine Connected to API.")
        except Exception as e:
            print(f"❌ Connection Error: {e}"); sys.exit()

    def _init_csv(self):
        """Creates the Master CSV File"""
        cols = [
            "Timestamp", "Spot_LTP", "Fut_LTP", "RSI", "VWAP", "EMA5", "EMA13",
            "ATM_Strike", "PCR",
            "CE_Symbol", "CE_LTP", "CE_OI", "CE_Delta", "CE_Theta",
            "PE_Symbol", "PE_LTP", "PE_OI", "PE_Delta", "PE_Theta"
        ]
        with open(self.log_file, 'w') as f:
            f.write(",".join(cols) + "\n")
        print(f"📝 Logging Data to: {self.log_file}")

    def update(self):
        """
        CALL THIS FUNCTION IN YOUR LOOP.
        It fetches all data, updates variables, and saves to CSV.
        """
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 1. Fetch Spot Indicators (RSI, EMA)
        self._fetch_spot()
        
        # 2. Fetch Future Indicators (VWAP)
        self._fetch_future()
        
        # 3. Calculate ATM
        if self.spot_ltp > 0:
            self.atm_strike = round(self.spot_ltp / 50) * 50
        
        # 4. Fetch Chain & Greeks
        if self.atm_strike > 0:
            self._fetch_chain()
            
        # 5. AUTO-SAVE TO CSV
        self._save_snapshot()

    def _fetch_spot(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            resp = self.groww.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "5minute")
            if not resp: return

            df = pd.DataFrame(resp['candles'], columns=['t','o','h','l','c','v','oi'])
            self.spot_ltp = df['c'].iloc[-1]
            
            # EMA
            self.ema5 = df['c'].ewm(span=5, adjust=False).mean().iloc[-1]
            self.ema13 = df['c'].ewm(span=13, adjust=False).mean().iloc[-1]
            
            # RSI
            delta = df['c'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            self.rsi = 100 - (100 / (1 + rs)).iloc[-1]
        except Exception as e:
            print(f"⚠️ Spot Error: {e}")

    def _fetch_future(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            resp = self.groww.get_historical_candles("NSE", "FNO", self.fut_symbol, start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "5minute")
            if not resp: return

            df = pd.DataFrame(resp['candles'], columns=['t','o','h','l','c','v','oi'])
            self.fut_ltp = df['c'].iloc[-1]
            self.vwap = (df['c'] * df['v']).cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
        except Exception as e:
            # print(f"⚠️ Future Error: {e}") 
            pass

    def _fetch_chain(self):
        try:
            chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
            if not chain or 'strikes' not in chain: return

            ce_oi_total = 0
            pe_oi_total = 0
            
            # Reset ATM Data
            self.atm_ce = {'symbol': '', 'ltp': 0, 'oi': 0, 'delta': 0, 'theta': 0}
            self.atm_pe = {'symbol': '', 'ltp': 0, 'oi': 0, 'delta': 0, 'theta': 0}

            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                # Update Totals for PCR
                ce_node = data.get('CE', {})
                pe_node = data.get('PE', {})
                ce_oi_total += ce_node.get('open_interest', 0)
                pe_oi_total += pe_node.get('open_interest', 0)
                
                # Extract ATM Data
                if strike == self.atm_strike:
                    # CE ATM
                    if ce_node:
                        greeks = ce_node.get('greeks', {})
                        self.atm_ce = {
                            'symbol': ce_node.get('trading_symbol', ''),
                            'ltp': ce_node.get('ltp', 0),
                            'oi': ce_node.get('open_interest', 0),
                            'delta': greeks.get('delta', 0),
                            'theta': greeks.get('theta', 0)
                        }
                    # PE ATM
                    if pe_node:
                        greeks = pe_node.get('greeks', {})
                        self.atm_pe = {
                            'symbol': pe_node.get('trading_symbol', ''),
                            'ltp': pe_node.get('ltp', 0),
                            'oi': pe_node.get('open_interest', 0),
                            'delta': greeks.get('delta', 0),
                            'theta': greeks.get('theta', 0)
                        }

            # PCR Calc
            self.pcr = round(pe_oi_total / ce_oi_total, 2) if ce_oi_total > 0 else 0

        except Exception as e:
            print(f"⚠️ Chain Error: {e}")

    def _save_snapshot(self):
        """Writes the current state of the Engine to CSV"""
        row = [
            self.timestamp,
            self.spot_ltp, self.fut_ltp, int(self.rsi), round(self.vwap, 2), round(self.ema5, 2), round(self.ema13, 2),
            self.atm_strike, self.pcr,
            self.atm_ce['symbol'], self.atm_ce['ltp'], self.atm_ce['oi'], self.atm_ce['delta'], self.atm_ce['theta'],
            self.atm_pe['symbol'], self.atm_pe['ltp'], self.atm_pe['oi'], self.atm_pe['delta'], self.atm_pe['theta']
        ]
        try:
            with open(self.log_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except: pass