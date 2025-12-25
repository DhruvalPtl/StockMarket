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

        # 3. TRACKING & DEBUG
        self.update_count = 0
        self.last_spot_update = None
        self.last_chain_update = None
        self.errors = {'spot': 0, 'future': 0, 'chain': 0}

        # 4. SETUP AUTO-LOGGING
        self.log_file = f"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_engine_log\\Engine_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv()
        
        # 5. CONNECT
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
        self.update_count += 1
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Show progress every update
        print(f"\r⏳ Update #{self.update_count} | {self.timestamp} | Fetching data...", end='', flush=True)
        
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
        
        # 6. PRINT LIVE STATUS
        self._print_status()

    def _fetch_spot(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            resp = self.groww.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY", 
                start.strftime("%Y-%m-%d %H:%M:%S"), 
                end.strftime("%Y-%m-%d %H:%M:%S"), 
                "5minute"
            )
            
            if not resp or 'candles' not in resp:
                self.errors['spot'] += 1
                return

            df = pd.DataFrame(resp['candles'], columns=['t','o','h','l','c','v','oi'])
            
            if len(df) == 0:
                return
            
            self.spot_ltp = df['c'].iloc[-1]
            self.last_spot_update = datetime.now()
            
            # EMA
            if len(df) >= 13:
                self.ema5 = df['c'].ewm(span=5, adjust=False).mean().iloc[-1]
                self.ema13 = df['c'].ewm(span=13, adjust=False).mean().iloc[-1]
            
            # RSI
            if len(df) >= 15:
                delta = df['c'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                self.rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
        except Exception as e:
            self.errors['spot'] += 1
            if self.errors['spot'] % 10 == 1:  # Print every 10th error
                print(f"\n⚠️ Spot Error #{self.errors['spot']}: {e}")

    def _fetch_future(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=2)
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", self.fut_symbol, 
                start.strftime("%Y-%m-%d %H:%M:%S"), 
                end.strftime("%Y-%m-%d %H:%M:%S"), 
                "5minute"
            )
            
            if not resp or 'candles' not in resp:
                self.errors['future'] += 1
                return

            df = pd.DataFrame(resp['candles'], columns=['t','o','h','l','c','v','oi'])
            
            if len(df) == 0:
                return
                
            self.fut_ltp = df['c'].iloc[-1]
            
            # VWAP calculation
            if df['v'].sum() > 0:
                self.vwap = (df['c'] * df['v']).sum() / df['v'].sum()
            
        except Exception as e:
            self.errors['future'] += 1
            if self.errors['future'] % 10 == 1:
                print(f"\n⚠️ Future Error #{self.errors['future']}: {e}")

    def _fetch_chain(self):
        try:
            chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
            
            if not chain or 'strikes' not in chain:
                self.errors['chain'] += 1
                return

            self.last_chain_update = datetime.now()
            
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
            self.errors['chain'] += 1
            if self.errors['chain'] % 10 == 1:
                print(f"\n⚠️ Chain Error #{self.errors['chain']}: {e}")

    def _save_snapshot(self):
        """Writes the current state of the Engine to CSV"""
        row = [
            self.timestamp,
            self.spot_ltp, self.fut_ltp, int(self.rsi), round(self.vwap, 2), 
            round(self.ema5, 2), round(self.ema13, 2),
            self.atm_strike, self.pcr,
            self.atm_ce['symbol'], self.atm_ce['ltp'], self.atm_ce['oi'], 
            round(self.atm_ce['delta'], 4), round(self.atm_ce['theta'], 4),
            self.atm_pe['symbol'], self.atm_pe['ltp'], self.atm_pe['oi'], 
            round(self.atm_pe['delta'], 4), round(self.atm_pe['theta'], 4)
        ]
        try:
            with open(self.log_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"\n❌ Log Error: {e}")

    def _print_status(self):
        """Print live data status - VISUAL FEEDBACK"""
        # Clear previous line and print new status
        print("\r" + " " * 120, end='')  # Clear line
        
        status_parts = []
        
        # Spot status
        if self.spot_ltp > 0:
            status_parts.append(f"📊 Nifty: {self.spot_ltp:.2f}")
        else:
            status_parts.append("📊 Nifty: ⏳")
        
        # RSI status
        if self.rsi > 0:
            rsi_emoji = "🔥" if self.rsi > 60 else "🧊" if self.rsi < 40 else "➖"
            status_parts.append(f"RSI: {int(self.rsi)}{rsi_emoji}")
        
        # ATM status
        if self.atm_strike > 0:
            status_parts.append(f"ATM: {self.atm_strike}")
            
            # Show option prices if available
            if self.atm_ce['ltp'] > 0:
                status_parts.append(f"CE: ₹{self.atm_ce['ltp']:.2f}")
            if self.atm_pe['ltp'] > 0:
                status_parts.append(f"PE: ₹{self.atm_pe['ltp']:.2f}")
        
        # PCR status
        if self.pcr > 0:
            pcr_emoji = "🐂" if self.pcr > 1.1 else "🐻" if self.pcr < 0.9 else "⚖️"
            status_parts.append(f"PCR: {self.pcr}{pcr_emoji}")
        
        # Data freshness
        if self.last_spot_update:
            age = (datetime.now() - self.last_spot_update).seconds
            if age < 30:
                status_parts.append("✅ LIVE")
            else:
                status_parts.append(f"⚠️ Stale ({age}s)")
        
        print("\r" + " | ".join(status_parts), end='', flush=True)

    def get_health_status(self):
        """Returns engine health for monitoring"""
        return {
            'updates': self.update_count,
            'spot_errors': self.errors['spot'],
            'future_errors': self.errors['future'],
            'chain_errors': self.errors['chain'],
            'last_spot_update': self.last_spot_update,
            'last_chain_update': self.last_chain_update,
            'data_quality': 'GOOD' if (self.spot_ltp > 0 and self.atm_strike > 0) else 'POOR'
        }