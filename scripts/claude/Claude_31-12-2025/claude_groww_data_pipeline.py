"""
COMPLETE FIXED GROWW DATA PIPELINE v2.0
✅ Proper RSI calculation (Wilder's smoothing)
✅ Full day VWAP (from 9:15 AM, not last 5 mins)
✅ Typical Price for VWAP (H+L+C)/3
✅ Division by zero protection
✅ Debug logging for verification
✅ OI change tracking
✅ All Greeks included
✅ Rate limiting
"""

import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta, time
import sys
import os
import time as time_module


class GrowwDataEngine:
    def __init__(self, api_key, api_secret, expiry_date, fut_symbol):
        print(f"\n⚙️ STARTING ENGINE v2.0 | Expiry: {expiry_date} | Future: {fut_symbol}")
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.expiry_date = expiry_date
        self.fut_symbol = fut_symbol
        
        # Date format setup
        try:
            self.dt = datetime.strptime(expiry_date, "%Y-%m-%d")
            self.sym_date = self.dt.strftime("%d%b%y")
        except ValueError:
            print("❌ CRITICAL:  Expiry must be YYYY-MM-DD")
            sys.exit()
        
        # Public variables
        self.timestamp = None
        self.spot_ltp = 0.0
        self.fut_ltp = 0.0
        self.rsi = 50.0  # Start at neutral
        self.ema5 = 0.0
        self.ema13 = 0.0
        self.vwap = 0.0
        self.atm_strike = 0
        self.pcr = 0.0
        
        # ATM Option containers
        self.atm_ce = {
            'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
            'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
        }
        self.atm_pe = {
            'symbol': '', 'strike': 0, 'ltp':  0, 'oi': 0,
            'delta': 0, 'theta': 0, 'gamma':  0, 'vega': 0, 'iv':  0
        }
        
        # Total OI
        self.total_ce_oi = 0
        self.total_pe_oi = 0
        
        # Previous values for change tracking
        self.prev = {
            'spot':  0,
            'ce_ltp': 0,
            'pe_ltp': 0,
            'ce_oi': 0,
            'pe_oi':  0,
            'pcr': 0
        }
        
        # Warmup tracking
        self.rsi_warmup_complete = False
        self.rsi_periods_needed = 15
        self.candles_processed = 0
        
        # Tracking & debug
        self.update_count = 0
        self.last_spot_update = None
        self.last_chain_update = None
        self.errors = {'spot': 0, 'future': 0, 'chain': 0}
        self.last_api_call = {'spot': 0, 'future': 0, 'chain': 0}
        
        # Debug mode (set to True to see RSI/VWAP calculations)
        self.debug_mode = False
        
        # CSV logging
        self.log_file = f"D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_engine_log\\Engine_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv()
        
        # Connect
        self._connect()
    
    def _connect(self):
        try:
            token = GrowwAPI.get_access_token(
                api_key=self.api_key,
                secret=self.api_secret
            )
            self.groww = GrowwAPI(token)
            print("✅ Engine Connected to API.")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            sys.exit()
    
    def _init_csv(self):
        """Create master CSV file"""
        cols = [
            "Timestamp", "Spot_LTP", "Fut_LTP", "RSI", "RSI_Ready", "VWAP", "EMA5", "EMA13",
            "ATM_Strike", "PCR", "Total_CE_OI", "Total_PE_OI",
            "CE_Symbol", "CE_Strike", "CE_LTP", "CE_OI", "CE_Delta", "CE_Gamma",
            "CE_Theta", "CE_Vega", "CE_IV",
            "PE_Symbol", "PE_Strike", "PE_LTP", "PE_OI", "PE_Delta", "PE_Gamma",
            "PE_Theta", "PE_Vega", "PE_IV"
        ]
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write(",".join(cols) + "\n")
        print(f"📝 Logging Data to:  {self.log_file}")
    
    def _rate_limit(self, api_type):
        """Rate limiting - prevent API throttling"""
        min_delay = {'spot': 0.5, 'future':  0.5, 'chain': 1.0}
        
        now = time_module.time()
        elapsed = now - self.last_api_call[api_type]
        
        if elapsed < min_delay[api_type]: 
            time_module.sleep(min_delay[api_type] - elapsed)
        
        self.last_api_call[api_type] = time_module.time()
    
    def _get_market_open_time(self):
        """Get today's market open time (9:15 AM)"""
        now = datetime.now()
        return now.replace(hour=9, minute=15, second=0, microsecond=0)
    
    def update(self):
        """Main update function - call in your loop"""
        self.update_count += 1
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\r⏳ Update #{self.update_count} | {self.timestamp} | Fetching.. .", end='', flush=True)
        
        # Fetch data
        self._rate_limit('spot')
        self._fetch_spot()
        
        self._rate_limit('future')
        self._fetch_future()
        
        # Calculate ATM
        if self.spot_ltp > 0:
            self.atm_strike = round(self.spot_ltp / 50) * 50
        
        # Fetch chain & Greeks
        if self.atm_strike > 0:
            self._rate_limit('chain')
            self._fetch_chain()
        
        # Auto-save
        self._save_snapshot()
        
        # Print status
        self._print_status()
    
    def _fetch_spot(self):
        """
        Fetch spot data for RSI/EMA calculation
        ✅ Uses full day data from 9:15 AM
        ✅ Wilder's RSI smoothing method
        ✅ Division by zero protection
        """
        try: 
            end = datetime.now()
            today_open = self._get_market_open_time()
            
            # Fetch from market open for full day data
            resp = self.groww.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY",
                today_open.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"),
                "1minute"  # 1-minute candles for accuracy
            )
            
            if not resp or 'candles' not in resp:
                self.errors['spot'] += 1
                return
            
            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) == 7:
                cols.append('oi')
            df.columns = cols[: len(df.columns)]
            
            if len(df) == 0:
                return
            
            # Latest price
            self.spot_ltp = float(df['c'].iloc[-1])
            self.last_spot_update = datetime.now()
            
            # Track candles processed
            self.candles_processed = len(df)
            
            # EMA calculation (need 13+ candles)
            if len(df) >= 13:
                self.ema5 = float(df['c'].ewm(span=5, adjust=False).mean().iloc[-1])
                self.ema13 = float(df['c'].ewm(span=13, adjust=False).mean().iloc[-1])
            
            # RSI calculation (need 15+ candles)
            if len(df) >= self.rsi_periods_needed:
                self.rsi = self._calculate_rsi(df['c'])
                
                if not self.rsi_warmup_complete: 
                    self.rsi_warmup_complete = True
                    print(f"\n✅ RSI Warmup Complete ({len(df)} candles, RSI: {self.rsi:.1f})")
            else:
                self.rsi = 50  # Neutral during warmup
        
        except Exception as e:
            self.errors['spot'] += 1
            if self.errors['spot'] % 10 == 1:
                print(f"\n⚠️ Spot Error #{self.errors['spot']}: {e}")
    
    def _calculate_rsi(self, close_prices, period=14):
        """
        Calculate RSI using Wilder's Smoothing Method
        
        Formula: 
        1. Calculate price changes (delta)
        2. Separate gains and losses
        3. Use EMA with alpha = 1/period (Wilder's smoothing)
        4. RS = Avg Gain / Avg Loss
        5. RSI = 100 - (100 / (1 + RS))
        """
        try:
            # Step 1: Calculate price changes
            delta = close_prices.diff()
            
            # Step 2: Separate gains and losses
            gains = delta.where(delta > 0, 0.0)
            losses = (-delta.where(delta < 0, 0.0))
            
            # Step 3: Wilder's smoothing (EMA with alpha = 1/period)
            alpha = 1.0 / period
            avg_gain = gains.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
            avg_loss = losses.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
            
            # Step 4: Calculate RS (protect against division by zero)
            last_avg_gain = float(avg_gain.iloc[-1])
            last_avg_loss = float(avg_loss.iloc[-1])
            
            if last_avg_loss == 0:
                if last_avg_gain == 0:
                    rsi = 50.0  # No movement = neutral
                else: 
                    rsi = 100.0  # All gains, no losses
            else:
                rs = last_avg_gain / last_avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))
            
            # Validate RSI is within bounds
            rsi = max(0.0, min(100.0, rsi))
            
            # Debug output
            if self.debug_mode:
                print(f"\n🔍 RSI DEBUG:")
                print(f"   Candles: {len(close_prices)}")
                print(f"   Last 5 closes: {close_prices.tail().tolist()}")
                print(f"   Avg Gain:  {last_avg_gain:.4f}")
                print(f"   Avg Loss: {last_avg_loss:.4f}")
                print(f"   RS: {last_avg_gain/max(last_avg_loss, 0.0001):.4f}")
                print(f"   RSI:  {rsi:.2f}")
            
            return rsi
        
        except Exception as e:
            print(f"\n⚠️ RSI Calculation Error: {e}")
            return 50.0  # Return neutral on error
    
    def _fetch_future(self):
        """
        Fetch futures data for VWAP calculation
        ✅ Uses FULL DAY data from 9:15 AM
        ✅ Proper VWAP with Typical Price (H+L+C)/3
        ✅ Volume-weighted calculation
        """
        try:
            end = datetime.now()
            today_open = self._get_market_open_time()
            
            # Fetch FULL DAY data from 9:15 AM
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", self.fut_symbol,
                today_open.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"),
                "1minute"  # 1-minute candles
            )
            
            if not resp or 'candles' not in resp: 
                self.errors['future'] += 1
                return
            
            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) == 7:
                cols.append('oi')
            df.columns = cols[: len(df.columns)]
            
            if len(df) == 0:
                return
            
            # Latest futures price
            self.fut_ltp = float(df['c'].iloc[-1])
            
            # Calculate VWAP
            self.vwap = self._calculate_vwap(df)
        
        except Exception as e:
            self.errors['future'] += 1
            if self.errors['future'] % 10 == 1:
                print(f"\n⚠️ Future Error #{self.errors['future']}: {e}")
    
    def _calculate_vwap(self, df):
        """
        Calculate VWAP (Volume Weighted Average Price)
        
        Formula: 
        VWAP = Σ(Typical Price × Volume) / Σ(Volume)
        
        Where Typical Price = (High + Low + Close) / 3
        """
        try: 
            # Check if volume data exists
            if 'v' not in df.columns:
                # Fallback:  simple average of close prices
                return float(df['c'].mean())
            
            total_volume = df['v'].sum()
            
            if total_volume == 0:
                # No volume data, use simple average
                return float(df['c'].mean())
            
            # Calculate Typical Price = (High + Low + Close) / 3
            df = df.copy()  # Avoid SettingWithCopyWarning
            df['typical_price'] = (df['h'] + df['l'] + df['c']) / 3.0
            
            # Calculate VWAP = Σ(TP × Volume) / Σ(Volume)
            df['tp_volume'] = df['typical_price'] * df['v']
            vwap = df['tp_volume'].sum() / total_volume
            
            # Debug output
            if self.debug_mode:
                print(f"\n🔍 VWAP DEBUG:")
                print(f"   Candles: {len(df)}")
                print(f"   Total Volume: {total_volume: ,.0f}")
                print(f"   First TP: {df['typical_price'].iloc[0]:.2f}")
                print(f"   Last TP: {df['typical_price'].iloc[-1]:.2f}")
                print(f"   Current Fut:  {self.fut_ltp:.2f}")
                print(f"   VWAP: {vwap:.2f}")
                print(f"   Difference: {self.fut_ltp - vwap:+.2f}")
            
            return float(vwap)
        
        except Exception as e: 
            print(f"\n⚠️ VWAP Calculation Error: {e}")
            return float(df['c'].mean()) if len(df) > 0 else 0.0
    
    def _fetch_chain(self):
        """Fetch option chain and SAVE IT for symbol lookup"""
        try: 
            chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
            
            if not chain or 'strikes' not in chain:
                self.errors['chain'] += 1
                return
            
            self.last_chain_update = datetime.now()
            
            # [CRITICAL ADDITION] Save the raw chain data for symbol lookup
            self.chain_data = chain['strikes'] 
            
            ce_oi_total = 0
            pe_oi_total = 0
            
            # Reset ATM containers
            self.atm_ce = {
                'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
                'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
            }
            self.atm_pe = {
                'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
                'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
            }
            
            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                ce_node = data.get('CE', {})
                pe_node = data.get('PE', {})
                
                # Sum totals for PCR
                ce_oi_total += ce_node.get('open_interest', 0)
                pe_oi_total += pe_node.get('open_interest', 0)
                
                # Extract ATM
                if strike == self.atm_strike:
                    if ce_node: 
                        greeks = ce_node.get('greeks', {})
                        self.atm_ce = {
                            'symbol': ce_node.get('trading_symbol', ''),
                            'strike': int(strike),
                            'ltp': ce_node.get('ltp', 0),
                            'oi': ce_node.get('open_interest', 0),
                            'delta': greeks.get('delta', 0),
                            'gamma': greeks.get('gamma', 0),
                            'theta': greeks.get('theta', 0),
                            'vega': greeks.get('vega', 0),
                            'iv': greeks.get('iv', 0)
                        }
                    
                    if pe_node:
                        greeks = pe_node.get('greeks', {})
                        self.atm_pe = {
                            'symbol': pe_node.get('trading_symbol', ''),
                            'strike': int(strike),
                            'ltp': pe_node.get('ltp', 0),
                            'oi': pe_node.get('open_interest', 0),
                            'delta': greeks.get('delta', 0),
                            'gamma': greeks.get('gamma', 0),
                            'theta': greeks.get('theta', 0),
                            'vega': greeks.get('vega', 0),
                            'iv': greeks.get('iv', 0)
                        }
            
            # Store totals
            self.total_ce_oi = ce_oi_total
            self.total_pe_oi = pe_oi_total
            
            # PCR
            self.pcr = round(pe_oi_total / ce_oi_total, 2) if ce_oi_total > 0 else 0
        
        except Exception as e:
            self.errors['chain'] += 1
            if self.errors['chain'] % 10 == 1:
                print(f"\n⚠️ Chain Error #{self.errors['chain']}: {e}")

    # [ADD THIS NEW HELPER METHOD TO THE CLASS]
    def get_strike_data(self, strike):
        """Helper to get full data for a specific strike from cache"""
        if hasattr(self, 'chain_data') and self.chain_data:
            # Groww returns keys as strings (e.g., "25000.00")
            # Try exact match first, then formatted string
            str_strike = str(float(strike))
            # Also try integer string for robustness
            int_strike = str(int(strike))
            
            if str_strike in self.chain_data:
                return self.chain_data[str_strike]
            elif int_strike in self.chain_data:
                return self.chain_data[int_strike]
        return None
    
    def _save_snapshot(self):
        """Save current state to CSV"""
        row = [
            self.timestamp,
            self.spot_ltp, self.fut_ltp,
            round(self.rsi, 1), self.rsi_warmup_complete,
            round(self.vwap, 2),
            round(self.ema5, 2), round(self.ema13, 2),
            self.atm_strike, self.pcr,
            self.total_ce_oi, self.total_pe_oi,
            self.atm_ce['symbol'], self.atm_ce['strike'], self.atm_ce['ltp'],
            self.atm_ce['oi'], round(self.atm_ce['delta'], 4),
            round(self.atm_ce['gamma'], 6), round(self.atm_ce['theta'], 4),
            round(self.atm_ce['vega'], 4), round(self.atm_ce['iv'], 2),
            self.atm_pe['symbol'], self.atm_pe['strike'], self.atm_pe['ltp'],
            self.atm_pe['oi'], round(self.atm_pe['delta'], 4),
            round(self.atm_pe['gamma'], 6), round(self.atm_pe['theta'], 4),
            round(self.atm_pe['vega'], 4), round(self.atm_pe['iv'], 2)
        ]
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(",".join(map(str, row)) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"\n❌ Log Error: {e}")
    
    def _print_status(self):
        """Print live status"""
        print("\r" + " " * 120, end='')
        
        status = []
        
        # Warmup indicator
        if not self.rsi_warmup_complete: 
            status.append(f"⏳ WARMUP ({self.candles_processed}/{self.rsi_periods_needed})")
        else:
            status.append("✅ LIVE")
        
        if self.spot_ltp > 0:
            status.append(f"📊 Nifty: {self.spot_ltp:.2f}")
        
        if self.vwap > 0:
            vwap_diff = self.spot_ltp - self.vwap
            vwap_signal = "🟢" if vwap_diff > 0 else "🔴"
            status.append(f"VWAP: {self.vwap:.2f} {vwap_signal}({vwap_diff:+.1f})")
        
        if self.rsi > 0:
            if self.rsi > 60:
                rsi_emoji = "🔥"
            elif self.rsi < 40:
                rsi_emoji = "🧊"
            else:
                rsi_emoji = "➖"
            status.append(f"RSI: {self.rsi:.1f}{rsi_emoji}")
        
        if self.atm_strike > 0:
            status.append(f"ATM: {self.atm_strike}")
            
            if self.atm_ce['ltp'] > 0:
                status.append(f"CE:  Rs. {self.atm_ce['ltp']:.2f}")
            if self.atm_pe['ltp'] > 0:
                status.append(f"PE: Rs. {self.atm_pe['ltp']:.2f}")
        
        if self.pcr > 0:
            pcr_emoji = "🐂" if self.pcr > 1.1 else "🐻" if self.pcr < 0.9 else "⚖️"
            status.append(f"PCR: {self.pcr}{pcr_emoji}")
        
        print("\r" + " | ".join(status), end='', flush=True)
    
    def get_changes(self):
        """Calculate changes from previous tick"""
        changes = {
            'spot_change': self.spot_ltp - self.prev['spot'] if self.prev['spot'] > 0 else 0,
            'ce_price_change': self.atm_ce['ltp'] - self.prev['ce_ltp'] if self.prev['ce_ltp'] > 0 else 0,
            'pe_price_change':  self.atm_pe['ltp'] - self.prev['pe_ltp'] if self.prev['pe_ltp'] > 0 else 0,
            'ce_oi_change': self.atm_ce['oi'] - self.prev['ce_oi'] if self.prev['ce_oi'] > 0 else 0,
            'pe_oi_change':  self.atm_pe['oi'] - self.prev['pe_oi'] if self.prev['pe_oi'] > 0 else 0,
            'pcr_change': self.pcr - self.prev['pcr'] if self.prev['pcr'] > 0 else 0
        }
        
        # Update previous values
        self.prev = {
            'spot': self.spot_ltp,
            'ce_ltp': self.atm_ce['ltp'],
            'pe_ltp': self.atm_pe['ltp'],
            'ce_oi':  self.atm_ce['oi'],
            'pe_oi': self.atm_pe['oi'],
            'pcr': self.pcr
        }
        
        return changes
    
    def get_health_status(self):
        """Engine health check"""
        return {
            'updates': self.update_count,
            'candles':  self.candles_processed,
            'spot_errors': self.errors['spot'],
            'future_errors': self.errors['future'],
            'chain_errors': self.errors['chain'],
            'last_spot_update': self.last_spot_update,
            'last_chain_update':  self.last_chain_update,
            'rsi_ready': self.rsi_warmup_complete,
            'data_quality': 'GOOD' if (
                self.spot_ltp > 0 and
                self.atm_strike > 0 and
                self.vwap > 0 and
                self.rsi_warmup_complete and
                0 < self.rsi < 100
            ) else 'POOR'
        }
    
    def enable_debug(self):
        """Enable debug mode to see RSI/VWAP calculations"""
        self.debug_mode = True
        print("🔍 Debug mode ENABLED - RSI/VWAP calculations will be printed")
    
    def disable_debug(self):
        """Disable debug mode"""
        self.debug_mode = False
        print("🔍 Debug mode DISABLED")
        
    def get_strike_data(self, strike):
        """Helper to get full data for a specific strike from cache"""
        if hasattr(self, 'chain_data') and self.chain_data:
            # Groww returns keys as strings (e.g., "25000.00")
            # Try exact match first, then formatted string
            str_strike = str(float(strike))
            if str_strike in self.chain_data:
                return self.chain_data[str_strike]
        return None


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    """Test the data pipeline independently"""
    
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    EXPIRY_DATE = "2026-01-06"
    FUT_SYMBOL = "NSE-NIFTY-27Jan26-FUT"
    
    print("🧪 Testing Data Pipeline.. .\n")
    
    engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY_DATE, FUT_SYMBOL)
    # engine.enable_debug()  # Show RSI/VWAP calculations
    
    # Run 5 updates
    for i in range(5):
        print(f"\n--- Update {i+1} ---")
        engine.update()
        time_module.sleep(5)
    
    # Print health
    print(f"\n\n📊 Health Status:")
    health = engine.get_health_status()
    for key, value in health.items():
        print(f"   {key}: {value}")