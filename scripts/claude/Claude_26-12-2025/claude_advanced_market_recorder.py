"""
FIXED ADVANCED MARKET RECORDER
- Optimized strike range (±2000 points from spot)
- OI change tracking
- All Greeks included
- Rate limiting
"""

import time
import csv
import os
from datetime import datetime
from groww_data_pipeline import GrowwDataEngine

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTMwMzAsImlhdCI6MTc2NjU1MzAzMCwibmJmIjoxNzY2NTUzMDMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NTc2NzhiMS1mYjQxLTRkZjgtODc5Zi0yMDc3NTI2MTI5YzFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjEwYzcxYzg2LWM2NzYtNDRhMS05N2VmLTc0N2EzYzdmMTM3Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC41MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDk1MzAzMDAwNX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.qfClpvX56UsEn5qeLufKny_uF8ztmx0TA8WL2_FD_pLcv1l7kMkgec8lw997gwqHLXPu6YJPzdn4ECjXUwhYqQ"
API_SECRET = "84ENDHT5g1DQE86e2k8(Of*s4ukp!Ari"
EXPIRY     = "2025-12-30"

# Strike range configuration
STRIKE_RANGE = 2000  # ±2000 points from spot (instead of 13000-31000)

class FixedAdvancedRecorder:
    def __init__(self):
        print("\n" + "="*70)
        print("📹 FIXED ADVANCED MARKET RECORDER")
        print("   ✓ Optimized Strike Range")
        print("   ✓ OI Change Tracking")
        print("   ✓ All Greeks Included")
        print("="*70)
        
        # Initialize Engine
        fut_symbol = self._format_future_symbol(EXPIRY)
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY, fut_symbol)
        
        # Setup files
        date_str = datetime.now().strftime('%Y-%m-%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\market_recorder"
        os.makedirs(base_path, exist_ok=True)
        
        self.spot_file = f"{base_path}\\Spot_Data_{date_str}.csv"
        self.options_file = f"{base_path}\\Options_Data_{date_str}.csv"
        self.chain_file = f"{base_path}\\Optimized_Chain_{date_str}.csv"
        
        # Statistics
        self.tick_count = 0
        self.start_time = datetime.now()
        self.strikes_recorded = 0
        
        self._init_files()
        
        print(f"\n✅ Recorder Ready")
        print(f"📁 Spot Data: {self.spot_file}")
        print(f"📁 Options Data: {self.options_file}")
        print(f"📁 Chain Data: {self.chain_file}")
        print("="*70 + "\n")
    
    def _format_future_symbol(self, expiry):
        dt = datetime.strptime(expiry, "%Y-%m-%d")
        return f"NSE-NIFTY-{dt.strftime('%d%b%y')}-FUT"
    
    def _init_files(self):
        """Initialize CSV files"""
        
        # 1. Spot Data
        if not os.path.exists(self.spot_file):
            with open(self.spot_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Spot_Price", "Spot_Change", "Spot_Change_Pct",
                    "Future_Price", "Basis", "Basis_Pct",
                    "RSI", "RSI_Signal", "EMA5", "EMA13", "EMA_Crossover",
                    "VWAP", "Distance_From_VWAP", "VWAP_Signal"
                ])
        
        # 2. Options Data (with ALL Greeks)
        if not os.path.exists(self.options_file):
            with open(self.options_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "ATM_Strike", "PCR_Ratio", "PCR_Signal",
                    "Total_CE_OI", "Total_PE_OI",
                    # CE Data
                    "CE_Symbol", "CE_Price", "CE_Change", "CE_Change_Pct",
                    "CE_OI", "CE_OI_Change", "CE_OI_Change_Pct",
                    "CE_Delta", "CE_Gamma", "CE_Theta", "CE_Vega", "CE_IV",
                    # PE Data
                    "PE_Symbol", "PE_Price", "PE_Change", "PE_Change_Pct",
                    "PE_OI", "PE_OI_Change", "PE_OI_Change_Pct",
                    "PE_Delta", "PE_Gamma", "PE_Theta", "PE_Vega", "PE_IV",
                    # Signals
                    "OI_Signal", "Momentum_Signal"
                ])
        
        # 3. Optimized Chain (only relevant strikes)
        if not os.path.exists(self.chain_file):
            with open(self.chain_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Strike", "Type", "Symbol", "LTP",
                    "OI", "OI_Change", "Volume",
                    "Delta", "Gamma", "Theta", "Vega", "IV"
                ])
        
        print("✅ CSV Files Initialized")
    
    def record_tick(self):
        """Record one complete market snapshot"""
        self.tick_count += 1
        
        try:
            # Update engine
            self.engine.update()
            
            # Skip if no data
            if self.engine.spot_ltp == 0:
                return
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get changes
            changes = self.engine.get_changes()
            
            # Record Spot Data
            self._record_spot_data(timestamp, changes)
            
            # Record Options Data
            self._record_options_data(timestamp, changes)
            
            # Record Optimized Chain (every 30 seconds)
            if self.tick_count % 30 == 0:
                self._record_optimized_chain(timestamp)
            
            # Print status
            self._print_status()
            
        except Exception as e:
            print(f"\n❌ Recording Error: {e}")
    
    def _record_spot_data(self, timestamp, changes):
        """Record spot index and technical indicators"""
        spot = self.engine.spot_ltp
        if spot == 0:
            return
        
        # Calculate metrics
        spot_chg_pct = (changes['spot_change'] / spot * 100) if spot > 0 else 0
        basis = spot - self.engine.fut_ltp if self.engine.fut_ltp > 0 else 0
        basis_pct = (basis / spot * 100) if spot > 0 else 0
        
        # Signals
        rsi_signal = "Overbought" if self.engine.rsi > 70 else "Oversold" if self.engine.rsi < 30 else "Neutral"
        ema_cross = "Bullish" if self.engine.ema5 > self.engine.ema13 else "Bearish"
        vwap_dist = spot - self.engine.vwap if self.engine.vwap > 0 else 0
        vwap_signal = "Above" if spot > self.engine.vwap else "Below"
        
        row = [
            timestamp, spot, round(changes['spot_change'], 2), round(spot_chg_pct, 3),
            self.engine.fut_ltp, round(basis, 2), round(basis_pct, 3),
            int(self.engine.rsi), rsi_signal,
            round(self.engine.ema5, 2), round(self.engine.ema13, 2), ema_cross,
            round(self.engine.vwap, 2), round(vwap_dist, 2), vwap_signal
        ]
        
        with open(self.spot_file, 'a', newline='') as f:
            csv.writer(f).writerow(row)
    
    def _record_options_data(self, timestamp, changes):
        """Record ATM options with ALL Greeks"""
        if self.engine.atm_strike == 0:
            return
        
        # PCR Signal
        pcr_signal = "Bullish" if self.engine.pcr > 1.1 else "Bearish" if self.engine.pcr < 0.9 else "Neutral"
        
        # Get CE/PE data
        ce = self.engine.atm_ce
        pe = self.engine.atm_pe
        
        # Calculate % changes
        ce_chg_pct = (changes['ce_price_change'] / ce['ltp'] * 100) if ce['ltp'] > 0 else 0
        pe_chg_pct = (changes['pe_price_change'] / pe['ltp'] * 100) if pe['ltp'] > 0 else 0
        ce_oi_chg_pct = (changes['ce_oi_change'] / ce['oi'] * 100) if ce['oi'] > 0 else 0
        pe_oi_chg_pct = (changes['pe_oi_change'] / pe['oi'] * 100) if pe['oi'] > 0 else 0
        
        # OI Signal Analysis
        oi_signal = self._detect_oi_pattern(
            changes['ce_oi_change'], 
            changes['pe_oi_change'],
            changes['ce_price_change'],
            changes['pe_price_change']
        )
        
        # Momentum Signal
        momentum = "Strong_Bullish" if (self.engine.rsi > 60 and self.engine.spot_ltp > self.engine.vwap) else \
                   "Strong_Bearish" if (self.engine.rsi < 40 and self.engine.spot_ltp < self.engine.vwap) else \
                   "Bullish" if self.engine.spot_ltp > self.engine.vwap else \
                   "Bearish" if self.engine.spot_ltp < self.engine.vwap else "Neutral"
        
        row = [
            timestamp, self.engine.atm_strike, self.engine.pcr, pcr_signal,
            self.engine.total_ce_oi, self.engine.total_pe_oi,
            # CE
            ce['symbol'], ce['ltp'], round(changes['ce_price_change'], 2), round(ce_chg_pct, 3),
            ce['oi'], int(changes['ce_oi_change']), round(ce_oi_chg_pct, 3),
            round(ce['delta'], 4), round(ce['gamma'], 6), round(ce['theta'], 4),
            round(ce['vega'], 4), round(ce['iv'], 2),
            # PE
            pe['symbol'], pe['ltp'], round(changes['pe_price_change'], 2), round(pe_chg_pct, 3),
            pe['oi'], int(changes['pe_oi_change']), round(pe_oi_chg_pct, 3),
            round(pe['delta'], 4), round(pe['gamma'], 6), round(pe['theta'], 4),
            round(pe['vega'], 4), round(pe['iv'], 2),
            # Signals
            oi_signal, momentum
        ]
        
        with open(self.options_file, 'a', newline='') as f:
            csv.writer(f).writerow(row)
    
    def _detect_oi_pattern(self, ce_oi_chg, pe_oi_chg, ce_price_chg, pe_price_chg):
        """Detect OI-based patterns"""
        # Short Covering: CE OI falling + Price rising
        if ce_oi_chg < -1000 and ce_price_chg > 0:
            return "SHORT_COVERING"
        
        # Long Unwinding: PE OI falling + Price falling
        if pe_oi_chg < -1000 and pe_price_chg < 0:
            return "LONG_UNWINDING"
        
        # Fresh Long Building
        if ce_oi_chg > 1000 and ce_price_chg > 0:
            return "LONG_BUILDUP"
        
        # Fresh Short Building
        if pe_oi_chg > 1000 and pe_price_chg < 0:
            return "SHORT_BUILDUP"
        
        return "NEUTRAL"
    
    def _record_optimized_chain(self, timestamp):
        """Record ONLY relevant strikes (±2000 from spot)"""
        try:
            # Fetch full chain
            chain = self.engine.groww.get_option_chain("NSE", "NIFTY", EXPIRY)
            
            if not chain or 'strikes' not in chain:
                return
            
            spot = self.engine.spot_ltp
            min_strike = round(spot - STRIKE_RANGE, -2)
            max_strike = round(spot + STRIKE_RANGE, -2)
            
            rows = []
            strikes_count = 0
            
            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                # ONLY record strikes within range
                if not (min_strike <= strike <= max_strike):
                    continue
                
                strikes_count += 1
                
                # Record CE
                if 'CE' in data:
                    ce = data['CE']
                    greeks = ce.get('greeks', {})
                    rows.append([
                        timestamp, strike, 'CE',
                        ce.get('trading_symbol', ''),
                        ce.get('ltp', 0),
                        ce.get('open_interest', 0),
                        0,  # OI Change (can track if needed)
                        ce.get('volume', 0),
                        round(greeks.get('delta', 0), 4),
                        round(greeks.get('gamma', 0), 6),
                        round(greeks.get('theta', 0), 4),
                        round(greeks.get('vega', 0), 4),
                        round(greeks.get('iv', 0), 2)
                    ])
                
                # Record PE
                if 'PE' in data:
                    pe = data['PE']
                    greeks = pe.get('greeks', {})
                    rows.append([
                        timestamp, strike, 'PE',
                        pe.get('trading_symbol', ''),
                        pe.get('ltp', 0),
                        pe.get('open_interest', 0),
                        0,
                        pe.get('volume', 0),
                        round(greeks.get('delta', 0), 4),
                        round(greeks.get('gamma', 0), 6),
                        round(greeks.get('theta', 0), 4),
                        round(greeks.get('vega', 0), 4),
                        round(greeks.get('iv', 0), 2)
                    ])
            
            # Write all rows
            with open(self.chain_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            
            self.strikes_recorded = strikes_count
            print(f"\n✅ Optimized chain recorded ({strikes_count} strikes, range: {min_strike}-{max_strike})")
            
        except Exception as e:
            print(f"\n⚠️ Chain recording error: {e}")
    
    def _print_status(self):
        """Print recording status"""
        runtime = (datetime.now() - self.start_time).seconds
        
        status = [
            f"📹 #{self.tick_count}",
            f"⏱️ {runtime//60:02d}:{runtime%60:02d}",
            f"Spot: {self.engine.spot_ltp:.2f}",
            f"ATM: {self.engine.atm_strike}",
            f"RSI: {int(self.engine.rsi)}",
            f"PCR: {self.engine.pcr}"
        ]
        
        if self.strikes_recorded > 0:
            status.append(f"Strikes: {self.strikes_recorded}")
        
        print("\r" + " | ".join(status) + " " * 20, end='', flush=True)
    
    def run(self):
        """Main recording loop"""
        print("🎬 Recording Started...\n")
        
        try:
            while True:
                now = datetime.now()
                is_market = (
                    (now.hour == 9 and now.minute >= 15) or
                    (9 < now.hour < 15) or
                    (now.hour == 15 and now.minute <= 30)
                )
                
                if not is_market:
                    print(f"\r⏸️ Market Closed | {now.strftime('%H:%M:%S')}", end='')
                    time.sleep(30)
                    continue
                
                self.record_tick()
                time.sleep(1)
                
        except KeyboardInterrupt:
            runtime = (datetime.now() - self.start_time).seconds
            print(f"\n\n{'='*70}")
            print("🎬 Recording Stopped")
            print(f"{'='*70}")
            print(f"Total Ticks: {self.tick_count}")
            print(f"Runtime: {runtime//3600:02d}:{(runtime%3600)//60:02d}:{runtime%60:02d}")
            print(f"Avg Strikes/Record: {self.strikes_recorded}")
            print(f"{'='*70}\n")

if __name__ == "__main__":
    recorder = FixedAdvancedRecorder()
    recorder.run()