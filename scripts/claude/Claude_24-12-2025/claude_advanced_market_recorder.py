"""
ADVANCED MARKET RECORDER
Captures COMPLETE market data for backtesting and analysis
Records: Spot, Future, Options Chain, Greeks, OI, Volume, VWAP, RSI, EMA, PCR
"""

import time
import csv
import os
import sys
from datetime import datetime
from claude_groww_data_pipeline import GrowwDataEngine

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTMwMzAsImlhdCI6MTc2NjU1MzAzMCwibmJmIjoxNzY2NTUzMDMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NTc2NzhiMS1mYjQxLTRkZjgtODc5Zi0yMDc3NTI2MTI5YzFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjEwYzcxYzg2LWM2NzYtNDRhMS05N2VmLTc0N2EzYzdmMTM3Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC41MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDk1MzAzMDAwNX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.qfClpvX56UsEn5qeLufKny_uF8ztmx0TA8WL2_FD_pLcv1l7kMkgec8lw997gwqHLXPu6YJPzdn4ECjXUwhYqQ"
API_SECRET = "84ENDHT5g1DQE86e2k8(Of*s4ukp!Ari"  # Replace
EXPIRY     = "2025-12-30"  # Update weekly

class AdvancedMarketRecorder:
    def __init__(self):
        print("\n" + "="*70)
        print("📹 ADVANCED MARKET RECORDER - COMPLETE DATA CAPTURE")
        print("="*70)
        
        # Initialize Engine
        fut_symbol = self._format_future_symbol(EXPIRY)
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY, fut_symbol)
        
        # Setup file paths
        date_str = datetime.now().strftime('%Y-%m-%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude\\market_recorder"
        os.makedirs(base_path, exist_ok=True)
        
        # Create 3 separate files for organized data
        self.spot_file = f"{base_path}\\Spot_Data_{date_str}.csv"
        self.options_file = f"{base_path}\\Options_Data_{date_str}.csv"
        self.chain_file = f"{base_path}\\Full_Chain_{date_str}.csv"
        
        # Tracking
        self.last_spot = 0
        self.tick_count = 0
        self.start_time = datetime.now()
        
        # Initialize all CSV files
        self._init_files()
        
        print(f"\n✅ Recorder Initialized")
        print(f"📁 Files Created:")
        print(f"   1. {self.spot_file}")
        print(f"   2. {self.options_file}")
        print(f"   3. {self.chain_file}")
        print("="*70 + "\n")
    
    def _format_future_symbol(self, expiry):
        """Convert YYYY-MM-DD to NSE-NIFTY-30DEC25-FUT"""
        dt = datetime.strptime(expiry, "%Y-%m-%d")
        return f"NSE-NIFTY-{dt.strftime('%d%b%y')}-FUT"
    
    def _init_files(self):
        """Initialize all CSV files with headers"""
        
        # 1. SPOT DATA FILE (Index + Technical Indicators)
        if not os.path.exists(self.spot_file):
            with open(self.spot_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp",
                    "Spot_Price",
                    "Spot_Change",          # Price change from last tick
                    "Spot_Change_Pct",      # % change from last tick
                    "Velocity",             # Absolute price movement speed
                    "Future_Price",         # Nifty Future price
                    "Basis",                # Spot - Future (premium/discount)
                    "RSI",                  # 14-period RSI
                    "RSI_Signal",           # Overbought/Oversold/Neutral
                    "EMA_5",                # 5-period EMA
                    "EMA_13",               # 13-period EMA
                    "EMA_Crossover",        # Bullish/Bearish/Neutral
                    "VWAP",                 # Volume Weighted Average Price
                    "Distance_From_VWAP",   # Spot - VWAP
                    "VWAP_Signal"           # Above/Below
                ])
        
        # 2. OPTIONS DATA FILE (ATM Options with Greeks)
        if not os.path.exists(self.options_file):
            with open(self.options_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp",
                    "ATM_Strike",
                    "PCR_Ratio",            # Put/Call Ratio (entire chain)
                    "PCR_Signal",           # Bullish/Bearish/Neutral
                    # CALL DATA
                    "ATM_CE_Symbol",
                    "ATM_CE_Price",
                    "ATM_CE_Change",        # Premium change from last tick
                    "ATM_CE_Change_Pct",    # % change
                    "ATM_CE_OI",            # Open Interest
                    "ATM_CE_OI_Change",     # OI change (will calculate live)
                    "ATM_CE_Volume",        # Volume (if available)
                    "ATM_CE_Delta",
                    "ATM_CE_Gamma",
                    "ATM_CE_Theta",
                    "ATM_CE_Vega",
                    "ATM_CE_IV",            # Implied Volatility
                    # PUT DATA
                    "ATM_PE_Symbol",
                    "ATM_PE_Price",
                    "ATM_PE_Change",
                    "ATM_PE_Change_Pct",
                    "ATM_PE_OI",
                    "ATM_PE_OI_Change",
                    "ATM_PE_Volume",
                    "ATM_PE_Delta",
                    "ATM_PE_Gamma",
                    "ATM_PE_Theta",
                    "ATM_PE_Vega",
                    "ATM_PE_IV",
                    # SIGNALS
                    "OI_Signal",            # Short Covering/Long Unwinding/Neutral
                    "Momentum_Signal"       # Overall market momentum
                ])
        
        # 3. FULL CHAIN DATA FILE (All strikes - recorded every 30 seconds)
        if not os.path.exists(self.chain_file):
            with open(self.chain_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp",
                    "Strike",
                    "Type",                 # CE or PE
                    "Symbol",
                    "LTP",
                    "OI",
                    "OI_Change",
                    "Volume",
                    "Delta",
                    "Gamma",
                    "Theta",
                    "Vega",
                    "IV"
                ])
        
        print("✅ CSV Files Initialized with Headers")
    
    def record_tick(self):
        """Record one complete market snapshot"""
        self.tick_count += 1
        
        try:
            # Update engine to fetch latest data
            self.engine.update()
            
            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Record Spot Data
            self._record_spot_data(timestamp)
            
            # Record Options Data
            self._record_options_data(timestamp)
            
            # Record Full Chain (every 30 seconds to avoid huge files)
            if self.tick_count % 30 == 0:
                self._record_full_chain(timestamp)
            
            # Print status
            self._print_status()
            
        except Exception as e:
            print(f"\n❌ Recording Error: {e}")
    
    def _record_spot_data(self, timestamp):
        """Record spot index and technical indicators"""
        spot = self.engine.spot_ltp
        if spot == 0:
            return
        
        # Calculate changes
        spot_change = spot - self.last_spot if self.last_spot > 0 else 0
        spot_change_pct = (spot_change / self.last_spot * 100) if self.last_spot > 0 else 0
        velocity = abs(spot_change)
        
        # Basis calculation
        basis = spot - self.engine.fut_ltp if self.engine.fut_ltp > 0 else 0
        
        # RSI Signal
        rsi_signal = "Overbought" if self.engine.rsi > 70 else "Oversold" if self.engine.rsi < 30 else "Neutral"
        
        # EMA Crossover
        if self.engine.ema5 > self.engine.ema13:
            ema_crossover = "Bullish"
        elif self.engine.ema5 < self.engine.ema13:
            ema_crossover = "Bearish"
        else:
            ema_crossover = "Neutral"
        
        # VWAP Distance
        vwap_dist = spot - self.engine.vwap if self.engine.vwap > 0 else 0
        vwap_signal = "Above" if spot > self.engine.vwap else "Below"
        
        row = [
            timestamp,
            spot,
            round(spot_change, 2),
            round(spot_change_pct, 3),
            round(velocity, 2),
            self.engine.fut_ltp,
            round(basis, 2),
            int(self.engine.rsi),
            rsi_signal,
            round(self.engine.ema5, 2),
            round(self.engine.ema13, 2),
            ema_crossover,
            round(self.engine.vwap, 2),
            round(vwap_dist, 2),
            vwap_signal
        ]
        
        with open(self.spot_file, 'a', newline='') as f:
            csv.writer(f).writerow(row)
        
        self.last_spot = spot
    
    def _record_options_data(self, timestamp):
        """Record ATM options data with Greeks"""
        if self.engine.atm_strike == 0:
            return
        
        # PCR Signal
        pcr_signal = "Bullish" if self.engine.pcr > 1.1 else "Bearish" if self.engine.pcr < 0.9 else "Neutral"
        
        # Get CE data
        ce = self.engine.atm_ce
        ce_change = 0  # Will implement tracking in next version
        ce_change_pct = 0
        ce_oi_change = 0
        
        # Get PE data
        pe = self.engine.atm_pe
        pe_change = 0
        pe_change_pct = 0
        pe_oi_change = 0
        
        # OI Signal Analysis
        # If CE OI falling + price rising = Short Covering (Bullish)
        # If PE OI falling + price falling = Long Unwinding (Bearish)
        oi_signal = "Neutral"  # Simplified for now
        
        # Momentum Signal (combined analysis)
        momentum_signal = "Neutral"
        if self.engine.rsi > 60 and self.engine.spot_ltp > self.engine.vwap:
            momentum_signal = "Strong_Bullish"
        elif self.engine.rsi < 40 and self.engine.spot_ltp < self.engine.vwap:
            momentum_signal = "Strong_Bearish"
        elif self.engine.spot_ltp > self.engine.vwap:
            momentum_signal = "Bullish"
        elif self.engine.spot_ltp < self.engine.vwap:
            momentum_signal = "Bearish"
        
        row = [
            timestamp,
            self.engine.atm_strike,
            self.engine.pcr,
            pcr_signal,
            # CE Data
            ce['symbol'],
            ce['ltp'],
            ce_change,
            ce_change_pct,
            ce['oi'],
            ce_oi_change,
            0,  # Volume (not available in current API)
            round(ce['delta'], 4),
            0,  # Gamma (add if available)
            round(ce['theta'], 4),
            0,  # Vega (add if available)
            0,  # IV (add if available)
            # PE Data
            pe['symbol'],
            pe['ltp'],
            pe_change,
            pe_change_pct,
            pe['oi'],
            pe_oi_change,
            0,  # Volume
            round(pe['delta'], 4),
            0,  # Gamma
            round(pe['theta'], 4),
            0,  # Vega
            0,  # IV
            # Signals
            oi_signal,
            momentum_signal
        ]
        
        with open(self.options_file, 'a', newline='') as f:
            csv.writer(f).writerow(row)
    
    def _record_full_chain(self, timestamp):
        """Record complete option chain (all strikes)"""
        try:
            # Fetch full chain
            chain = self.engine.groww.get_option_chain("NSE", "NIFTY", EXPIRY)
            
            if not chain or 'strikes' not in chain:
                return
            
            rows = []
            
            for strike_str, data in chain['strikes'].items():
                strike = float(strike_str)
                
                # Record CE
                if 'CE' in data:
                    ce = data['CE']
                    greeks = ce.get('greeks', {})
                    rows.append([
                        timestamp,
                        strike,
                        'CE',
                        ce.get('trading_symbol', ''),
                        ce.get('ltp', 0),
                        ce.get('open_interest', 0),
                        0,  # OI Change (calculate later)
                        ce.get('volume', 0),
                        round(greeks.get('delta', 0), 4),
                        round(greeks.get('gamma', 0), 4),
                        round(greeks.get('theta', 0), 4),
                        round(greeks.get('vega', 0), 4),
                        round(greeks.get('iv', 0), 4)
                    ])
                
                # Record PE
                if 'PE' in data:
                    pe = data['PE']
                    greeks = pe.get('greeks', {})
                    rows.append([
                        timestamp,
                        strike,
                        'PE',
                        pe.get('trading_symbol', ''),
                        pe.get('ltp', 0),
                        pe.get('open_interest', 0),
                        0,
                        pe.get('volume', 0),
                        round(greeks.get('delta', 0), 4),
                        round(greeks.get('gamma', 0), 4),
                        round(greeks.get('theta', 0), 4),
                        round(greeks.get('vega', 0), 4),
                        round(greeks.get('iv', 0), 4)
                    ])
            
            # Write all rows at once
            with open(self.chain_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            
            print(f"\n✅ Full chain recorded ({len(rows)} strikes)")
            
        except Exception as e:
            print(f"\n⚠️ Chain recording error: {e}")
    
    def _print_status(self):
        """Print real-time recording status"""
        # Calculate runtime
        runtime = (datetime.now() - self.start_time).seconds
        hours = runtime // 3600
        minutes = (runtime % 3600) // 60
        seconds = runtime % 60
        
        # Build status string
        status = [
            f"📹 REC #{self.tick_count}",
            f"⏱️  {hours:02d}:{minutes:02d}:{seconds:02d}",
            f"📊 Spot: {self.engine.spot_ltp:.2f}",
            f"ATM: {self.engine.atm_strike}",
            f"RSI: {int(self.engine.rsi)}",
            f"PCR: {self.engine.pcr}"
        ]
        
        # Add option prices if available
        if self.engine.atm_ce['ltp'] > 0:
            status.append(f"CE: Rs. {self.engine.atm_ce['ltp']:.2f}")
        if self.engine.atm_pe['ltp'] > 0:
            status.append(f"PE: Rs. {self.engine.atm_pe['ltp']:.2f}")
        
        # Print with carriage return (overwrites same line)
        print("\r" + " | ".join(status) + " " * 20, end='', flush=True)
    
    def run(self):
        """Main recording loop"""
        print("🎬 Recording Started...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Check market hours (9:15 AM to 3:30 PM)
                now = datetime.now()
                is_market_hours = (
                    (now.hour == 9 and now.minute >= 15) or
                    (9 < now.hour < 15) or
                    (now.hour == 15 and now.minute <= 30)
                )
                
                if not is_market_hours:
                    print(f"\r⏸️  Market Closed | Waiting... {now.strftime('%H:%M:%S')}", end='', flush=True)
                    time.sleep(30)
                    continue
                
                # Record tick
                self.record_tick()
                
                # Record every 1 second
                time.sleep(1)
                
        except KeyboardInterrupt:
            self._print_summary()
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _print_summary(self):
        """Print recording summary"""
        runtime = (datetime.now() - self.start_time).seconds
        
        print("\n\n" + "="*70)
        print("🎬 RECORDING STOPPED")
        print("="*70)
        print(f"Total Ticks:    {self.tick_count}")
        print(f"Runtime:        {runtime // 3600:02d}:{(runtime % 3600) // 60:02d}:{runtime % 60:02d}")
        print(f"Avg Rate:       {self.tick_count / max(runtime, 1):.2f} ticks/sec")
        print(f"\nFiles Saved:")
        print(f"  1. {self.spot_file}")
        print(f"  2. {self.options_file}")
        print(f"  3. {self.chain_file}")
        print("="*70 + "\n")


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print("\n⚠️  ENSURE MARKET IS OPEN BEFORE STARTING")
    print("This recorder captures live data every second.\n")
    
    input("Press ENTER to start recording...")
    
    recorder = AdvancedMarketRecorder()
    recorder.run()
