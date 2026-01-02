"""
ENHANCED GROWW DATA PIPELINE v3.0 - Multi-Strategy Support
✅ All original indicators preserved
✅ Added candle body, color for Strategy C
✅ Added previous row tracking for Strategy B
✅ All existing functionality intact
"""

import pandas as pd
import numpy as np
from growwapi import GrowwAPI
from datetime import datetime, timedelta, time
import sys
import os
import time as time_module


class GrowwDataEngine:
    def __init__(self, api_key, api_secret, expiry_date, fut_symbol, timeframe="1minute"):
        timeframe_map = {
            "1minute": "1min",
            "2minute": "2min", 
            "3minute": "3min",
            "5minute": "5min"
        }
        self.timeframe = timeframe
        self.timeframe_display = timeframe_map.get(timeframe, timeframe)
        
        print(f"\n⚙️ STARTING ENGINE v3.0 [{self.timeframe_display}] | Expiry: {expiry_date} | Future: {fut_symbol}")
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.expiry_date = expiry_date
        self.fut_symbol = fut_symbol
        
        # Date format setup
        try:
            self.dt = datetime.strptime(expiry_date, "%Y-%m-%d")
            self.sym_date = self.dt.strftime("%d%b%y")
        except ValueError:
            print("❌ CRITICAL: Expiry must be YYYY-MM-DD")
            sys.exit()
        
        # Public variables
        self.timestamp = None
        self.spot_ltp = 0.0
        self.fut_ltp = 0.0
        self.rsi = 50.0
        self.ema5 = 0.0
        self.ema13 = 0.0
        self.vwap = 0.0
        self.atm_strike = 0
        self.pcr = 0.0
        
        # NEW: Additional indicators for strategies
        self.fut_open = 0.0
        self.fut_high = 0.0
        self.fut_low = 0.0
        self.candle_body = 0.0
        self.candle_green = False
        
        # NEW: Previous tick data for Strategy B
        self.prev_fut_above_vwap = False
        
        # ATM Option containers
        self.atm_ce = {
            'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
            'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
        }
        self.atm_pe = {
            'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
            'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
        }
        
        # NEW: Multiple strikes storage (ATM ± 2 strikes)
        self.strikes_data = {}  # Format: {23500: {'CE': {...}, 'PE': {...}}, ...}
        
        # Total OI
        self.total_ce_oi = 0
        self.total_pe_oi = 0
        
        # Previous values for change tracking
        self.prev = {
            'spot': 0,
            'ce_ltp': 0,
            'pe_ltp': 0,
            'ce_oi': 0,
            'pe_oi': 0,
            'pcr': 0
        }
        
        # Warmup tracking
        self.rsi_warmup_complete = False
        self.rsi_periods_needed = 14
        self.candles_processed = 0
        
        # Tracking & debug
        self.update_count = 0
        self.last_spot_update = None
        self.last_chain_update = None
        self.errors = {'spot': 0, 'future': 0, 'chain': 0}
        self.last_api_call = {'spot': 0, 'future': 0, 'chain': 0}
        
        # Debug mode
        self.debug_mode = False
        
        # CSV logging
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
        """Create master CSV file with timeframe in filename"""
        cols = [
            "Timestamp", "Spot_LTP", "Fut_LTP", "Fut_Open", "Fut_High", "Fut_Low",
            "RSI", "RSI_Ready", "VWAP", "EMA5", "EMA13",
            "Candle_Body", "Candle_Green",
            "ATM_Strike", "PCR", "Total_CE_OI", "Total_PE_OI",
            "CE_Symbol", "CE_Strike", "CE_LTP", "CE_OI", "CE_Delta", "CE_Gamma",
            "CE_Theta", "CE_Vega", "CE_IV",
            "PE_Symbol", "PE_Strike", "PE_LTP", "PE_OI", "PE_Delta", "PE_Gamma",
            "PE_Theta", "PE_Vega", "PE_IV"
        ]
        
        # CHANGED: Add timeframe to log filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f"D:\\StockMarket\\StockMarket\\scripts\\claude\\expriment3\\claude_engine_log\\Engine_Log_{self.timeframe_display}_{timestamp}.csv"
        
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write(",".join(cols) + "\n")
        print(f"📝 [{self.timeframe_display}] Logging to: {self.log_file}")
    
    def _rate_limit(self, api_type):
        """Rate limiting - prevent API throttling"""
        min_delay = {'spot': 0.5, 'future': 0.5, 'chain': 1.0}
        
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
        
        print(f"\r⏳ Update #{self.update_count} | {self.timestamp} | Fetching...", end='', flush=True)
        
        # Store previous VWAP state for Strategy B
        self.prev_fut_above_vwap = (self.fut_ltp > self.vwap) if self.vwap > 0 else False
        
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
        """Fetch spot data for RSI/EMA calculation"""
        try:
            end = datetime.now()
            today_open = self._get_market_open_time()
            
            resp = self.groww.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY",
                today_open.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )
            
            if not resp or 'candles' not in resp:
                self.errors['spot'] += 1
                return
            
            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) == 7:
                cols.append('oi')
            df.columns = cols[:len(df.columns)]
            
            if len(df) == 0:
                return
            
            # Latest price
            self.spot_ltp = float(df['c'].iloc[-1])
            self.last_spot_update = datetime.now()
            
            # Track candles processed
            self.candles_processed = len(df)
            
            # EMA calculation
            if len(df) >= 13:
                self.ema5 = float(df['c'].ewm(span=5, adjust=False).mean().iloc[-1])
                self.ema13 = float(df['c'].ewm(span=13, adjust=False).mean().iloc[-1])
            
            # RSI calculation
            if len(df) >= self.rsi_periods_needed:
                self.rsi = self._calculate_rsi(df['c'])
                
                if not self.rsi_warmup_complete:
                    self.rsi_warmup_complete = True
                    print(f"\n✅ RSI Warmup Complete ({len(df)} candles, RSI: {self.rsi:.1f})")
            else:
                self.rsi = 50
        
        except Exception as e:
            self.errors['spot'] += 1
            if self.errors['spot'] % 10 == 1:
                print(f"\n⚠️ Spot Error #{self.errors['spot']}: {e}")
    
    def _calculate_rsi(self, close_prices, period=14):
        """Calculate RSI using Wilder's Smoothing Method"""
        try:
            delta = close_prices.diff()
            gains = delta.where(delta > 0, 0.0)
            losses = (-delta.where(delta < 0, 0.0))
            
            alpha = 1.0 / period
            avg_gain = gains.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
            avg_loss = losses.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
            
            last_avg_gain = float(avg_gain.iloc[-1])
            last_avg_loss = float(avg_loss.iloc[-1])
            
            if last_avg_loss == 0:
                if last_avg_gain == 0:
                    rsi = 50.0
                else:
                    rsi = 100.0
            else:
                rs = last_avg_gain / last_avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))
            
            rsi = max(0.0, min(100.0, rsi))
            
            if self.debug_mode:
                print(f"\n🔍 RSI DEBUG:")
                print(f"   Candles: {len(close_prices)}")
                print(f"   Last 5 closes: {close_prices.tail().tolist()}")
                print(f"   Avg Gain: {last_avg_gain:.4f}")
                print(f"   Avg Loss: {last_avg_loss:.4f}")
                print(f"   RS: {last_avg_gain/max(last_avg_loss, 0.0001):.4f}")
                print(f"   RSI: {rsi:.2f}")
            
            return rsi
        
        except Exception as e:
            print(f"\n⚠️ RSI Calculation Error: {e}")
            return 50.0
    
    def _fetch_future(self):    
        """Fetch futures data for VWAP and candle patterns"""
        try:
            end = datetime.now()
            today_open = self._get_market_open_time()
            
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", self.fut_symbol,
                today_open.strftime("%Y-%m-%d %H:%M:%S"),
                end.strftime("%Y-%m-%d %H:%M:%S"),
                self.timeframe
            )
            
            if not resp or 'candles' not in resp:
                self.errors['future'] += 1
                return
            
            df = pd.DataFrame(resp['candles'])
            cols = ['t', 'o', 'h', 'l', 'c', 'v']
            if len(df.columns) == 7:
                cols.append('oi')
            df.columns = cols[:len(df.columns)]
            
            if len(df) == 0:
                return
            
            # Latest candle data
            last_candle = df.iloc[-1]
            self.fut_ltp = float(last_candle['c'])
            self.fut_open = float(last_candle['o'])
            self.fut_high = float(last_candle['h'])
            self.fut_low = float(last_candle['l'])
            
            # NEW: Candle body and color for Strategy C
            self.candle_body = abs(self.fut_ltp - self.fut_open)
            self.candle_green = self.fut_ltp > self.fut_open
            
            # Calculate VWAP
            self.vwap = self._calculate_vwap(df)
        
        except Exception as e:
            self.errors['future'] += 1
            if self.errors['future'] % 10 == 1:
                print(f"\n⚠️ Future Error #{self.errors['future']}: {e}")
    
    def _calculate_vwap(self, df):
        """Calculate VWAP (Volume Weighted Average Price)"""
        try:
            if 'v' not in df.columns:
                print("⚠️  VWAP warning: Volume column missing, using mean price fallback")
                return float(df['c'].mean())
            
            total_volume = df['v'].sum()
            
            if total_volume == 0:
                return float(df['c'].mean())
            
            df = df.copy()
            df['typical_price'] = (df['h'] + df['l'] + df['c']) / 3.0
            df['tp_volume'] = df['typical_price'] * df['v']
            vwap = df['tp_volume'].sum() / total_volume
            
            if self.debug_mode:
                print(f"\n🔍 VWAP DEBUG:")
                print(f"   Candles: {len(df)}")
                print(f"   Total Volume: {total_volume:,.0f}")
                print(f"   First TP: {df['typical_price'].iloc[0]:.2f}")
                print(f"   Last TP: {df['typical_price'].iloc[-1]:.2f}")
                print(f"   Current Fut: {self.fut_ltp:.2f}")
                print(f"   VWAP: {vwap:.2f}")
                print(f"   Difference: {self.fut_ltp - vwap:+.2f}")
            
            return float(vwap)
        
        except Exception as e:
            print(f"\n⚠️ VWAP Calculation Error: {e}")
            return float(df['c'].mean()) if len(df) > 0 else 0.0
    
    """
    ENHANCED: _fetch_chain() with better error handling
    Location: enhanced_data_pipeline.py (replace existing method)
    """

    def _fetch_chain(self):
        """Fetch option chain with all Greeks - stores ATM ± 2 strikes"""
        try:
            chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
            
            if not chain or 'strikes' not in chain:
                self.errors['chain'] += 1
                return
            
            self.last_chain_update = datetime.now()
            
            ce_oi_total = 0
            pe_oi_total = 0
            
            # Reset ATM
            self.atm_ce = {
                'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
                'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
            }
            self.atm_pe = {
                'symbol': '', 'strike': 0, 'ltp': 0, 'oi': 0,
                'delta': 0, 'theta': 0, 'gamma': 0, 'vega': 0, 'iv': 0
            }
            
            # Clear strikes data
            self.strikes_data = {}
            
            # Define strikes to store (ATM ± 2 strikes)
            strikes_to_store = [
                self.atm_strike,       # ATM
                self.atm_strike + 50,  # OTM+1 for CE, ITM-1 for PE
                self.atm_strike + 100, # OTM+2 for CE, ITM-2 for PE
                self.atm_strike - 50,  # ITM-1 for CE, OTM+1 for PE
                self.atm_strike - 100  # ITM-2 for CE, OTM+2 for PE
            ]
            
            # ✅ ENHANCEMENT: Track which strikes were successfully loaded
            loaded_strikes = []
            
            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                ce_node = data.get('CE', {})
                pe_node = data.get('PE', {})
                
                # Sum totals for PCR
                ce_oi_total += ce_node.get('open_interest', 0)
                pe_oi_total += pe_node.get('open_interest', 0)
                
                # Store strikes data (ATM ± 2 strikes)
                if strike in strikes_to_store:
                    # ✅ FIX: Initialize strike dict even if CE/PE missing
                    if strike not in self.strikes_data:
                        self.strikes_data[int(strike)] = {}
                    
                    # ✅ FIX: Store CE only if valid data exists
                    if ce_node and ce_node.get('ltp', 0) > 0:
                        greeks = ce_node.get('greeks', {})
                        self.strikes_data[int(strike)]['CE'] = {
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
                        if int(strike) not in loaded_strikes:
                            loaded_strikes.append(int(strike))
                    
                    # ✅ FIX: Store PE only if valid data exists
                    if pe_node and pe_node.get('ltp', 0) > 0:
                        greeks = pe_node.get('greeks', {})
                        self.strikes_data[int(strike)]['PE'] = {
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
                        if int(strike) not in loaded_strikes:
                            loaded_strikes.append(int(strike))
                
                # Extract ATM (for backward compatibility)
                if strike == self.atm_strike:
                    if ce_node and ce_node.get('ltp', 0) > 0:
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
                    
                    if pe_node and pe_node.get('ltp', 0) > 0:
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
            
            # ✅ ENHANCEMENT: Log strike data coverage
            if self.debug_mode:
                print(f"\n📊 Chain Data Coverage:")
                print(f"   Target strikes: {strikes_to_store}")
                print(f"   Loaded strikes: {sorted(loaded_strikes)}")
                for strike in strikes_to_store:
                    if strike in self.strikes_data:
                        has_ce = 'CE' in self.strikes_data[strike]
                        has_pe = 'PE' in self.strikes_data[strike]
                        print(f"   {strike}: CE={has_ce}, PE={has_pe}")
        
        except Exception as e:
            self.errors['chain'] += 1
            if self.errors['chain'] % 10 == 1:
                print(f"\n⚠️ Chain Error #{self.errors['chain']}: {e}")
    
    def _save_snapshot(self):
        """Save current state to CSV"""
        row = [
            self.timestamp,
            self.spot_ltp, self.fut_ltp, self.fut_open, self.fut_high, self.fut_low,
            round(self.rsi, 1), self.rsi_warmup_complete,
            round(self.vwap, 2),
            round(self.ema5, 2), round(self.ema13, 2),
            round(self.candle_body, 2), self.candle_green,
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
        
        # Add timeframe indicator
        status.append(f"[{self.timeframe_display}]")
        
        # Warmup indicator
        if not self.rsi_warmup_complete:
            status.append(f"⏳ WARMUP ({self.candles_processed}/{self.rsi_periods_needed})")
        else:
            status.append("✅ LIVE")
        
        if self.spot_ltp > 0:
            status.append(f"📊 Nifty: {self.spot_ltp:.2f}")
        
        if self.vwap > 0:
            vwap_diff = self.fut_ltp - self.vwap
            vwap_signal = "🟢" if vwap_diff > 0 else "🔴"
            status.append(
                f"FUT_VWAP: {self.vwap:.2f} {vwap_signal}({vwap_diff:+.1f})"
            )

        
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
                status.append(f"CE: Rs.{self.atm_ce['ltp']:.2f}")
            if self.atm_pe['ltp'] > 0:
                status.append(f"PE: Rs.{self.atm_pe['ltp']:.2f}")
        
        if self.pcr > 0:
            pcr_emoji = "🐂" if self.pcr > 1.1 else "🐻" if self.pcr < 0.9 else "⚖️"
            status.append(f"PCR: {self.pcr}{pcr_emoji}")
        
        print("\r" + " | ".join(status), end='', flush=True)
    
    def get_changes(self):
        """Calculate changes from previous tick"""
        changes = {
            'spot_change': self.spot_ltp - self.prev['spot'] if self.prev['spot'] > 0 else 0,
            'ce_price_change': self.atm_ce['ltp'] - self.prev['ce_ltp'] if self.prev['ce_ltp'] > 0 else 0,
            'pe_price_change': self.atm_pe['ltp'] - self.prev['pe_ltp'] if self.prev['pe_ltp'] > 0 else 0,
            'ce_oi_change': self.atm_ce['oi'] - self.prev['ce_oi'] if self.prev['ce_oi'] > 0 else 0,
            'pe_oi_change': self.atm_pe['oi'] - self.prev['pe_oi'] if self.prev['pe_oi'] > 0 else 0,
            'pcr_change': self.pcr - self.prev['pcr'] if self.prev['pcr'] > 0 else 0
        }
        
        # Update previous values
        self.prev = {
            'spot': self.spot_ltp,
            'ce_ltp': self.atm_ce['ltp'],
            'pe_ltp': self.atm_pe['ltp'],
            'ce_oi': self.atm_ce['oi'],
            'pe_oi': self.atm_pe['oi'],
            'pcr': self.pcr
        }
        
        return changes
    
    def get_health_status(self):
        """Engine health check"""
        return {
            'updates': self.update_count,
            'candles': self.candles_processed,
            'spot_errors': self.errors['spot'],
            'future_errors': self.errors['future'],
            'chain_errors': self.errors['chain'],
            'last_spot_update': self.last_spot_update,
            'last_chain_update': self.last_chain_update,
            'rsi_ready': self.rsi_warmup_complete,
            'data_quality': 'GOOD' if (
                self.spot_ltp > 0 and
                self.atm_strike > 0 and
                self.vwap > 0 and
                self.rsi_warmup_complete and
                0 < self.rsi < 100
            ) else 'POOR'
        }
    
    """
    FIXED: get_affordable_strike() with robust fallback logic
    Location: enhanced_data_pipeline.py (replace existing method)
    """

    def get_affordable_strike(self, option_type, max_cost):
        """
        Find affordable strike within 2 strikes of ATM with robust fallback
        
        FIXES:
        1. ✅ Continues on zero premium instead of returning None
        2. ✅ Falls back to live API if strikes_data incomplete
        3. ✅ Handles missing strikes gracefully
        4. ✅ Validates all data before using
        
        Args:
            option_type: 'CE' or 'PE'
            max_cost: Maximum affordable cost (premium × lot_size)
        
        Returns:
            dict with strike data or None if none affordable
        """
        lot_size = 75
        
        # Define strike preference order
        if option_type == 'CE':
            # CE: Try ATM first, then move higher (OTM - cheaper)
            strikes_to_try = [
                self.atm_strike,       # ATM
                self.atm_strike + 50,  # OTM+1
                self.atm_strike + 100  # OTM+2
            ]
        else:  # PE
            # PE: Try ATM first, then move lower (OTM - cheaper)
            strikes_to_try = [
                self.atm_strike,       # ATM
                self.atm_strike - 50,  # OTM+1
                self.atm_strike - 100  # OTM+2
            ]
        
        # PHASE 1: Try cached strikes_data first (fast)
        for strike in strikes_to_try:
            # ✅ FIX: Check if strike exists AND has option_type
            if strike in self.strikes_data and option_type in self.strikes_data[strike]:
                option_data = self.strikes_data[strike][option_type]
                premium = option_data['ltp']
                
                # ✅ FIX: Skip zero premium but CONTINUE (don't return None)
                if premium == 0:
                    continue
                
                total_cost = premium * lot_size
                
                if total_cost <= max_cost:
                    # Found affordable strike in cache!
                    if strike != self.atm_strike:
                        print(f"\n💡 ATM expensive, using {option_type} @ {strike} (OTM) - Rs.{premium:.2f}")
                    return option_data
        
        # PHASE 2: Fallback to live API call if cache failed
        print(f"\n🔄 Cache incomplete, fetching live prices for {option_type}...")
        
        for strike in strikes_to_try:
            try:
                # Construct symbol for API call
                symbol = f"NIFTY{self.sym_date}{strike}{option_type}"
                search_key = f"NSE_{symbol}"
                
                # Get live LTP
                ltp_response = self.groww.get_ltp(
                    segment="FNO",
                    exchange_trading_symbols=search_key
                )
                
                if ltp_response and search_key in ltp_response:
                    premium = ltp_response[search_key]
                    
                    # ✅ FIX: Skip zero/invalid premium but continue
                    if premium <= 0:
                        continue
                    
                    total_cost = premium * lot_size
                    
                    if total_cost <= max_cost:
                        # Found affordable strike via API!
                        print(f"✅ Live API: {option_type} @ {strike} - Rs.{premium:.2f} (Total: Rs.{total_cost:.2f})")
                        
                        # Return data in same format as cached data
                        return {
                            'symbol': symbol,
                            'strike': strike,
                            'ltp': premium,
                            'oi': 0,  # OI not available in LTP call
                            'delta': 0,
                            'gamma': 0,
                            'theta': 0,
                            'vega': 0,
                            'iv': 0
                        }
            
            except Exception as e:
                # Don't crash on API error, try next strike
                print(f"⚠️ API error for {strike}: {e}")
                continue
        
        # PHASE 3: No affordable strike found
        print(f"\n❌ No affordable {option_type} found within 2 strikes of ATM")
        print(f"   Max budget: Rs.{max_cost:.2f}")
        print(f"   Tried strikes: {strikes_to_try}")
        return None
    
    def enable_debug(self):
        """Enable debug mode to see RSI/VWAP calculations"""
        self.debug_mode = True
        print("🔍 Debug mode ENABLED - RSI/VWAP calculations will be printed")
    
    def disable_debug(self):
        """Disable debug mode"""
        self.debug_mode = False
        print("🔍 Debug mode DISABLED")