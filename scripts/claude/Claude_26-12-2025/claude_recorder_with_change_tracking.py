"""
ADVANCED MARKET RECORDER v2.0
With Change Tracking, OI Analysis, and Real-time Alerts
"""

import time
import csv
import os
from datetime import datetime
from collections import deque
from claude_groww_data_pipeline import GrowwDataEngine

# ============================================================
# CONFIGURATION
# ============================================================
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTQwMDIsImlhdCI6MTc2NjU1NDAwMiwibmJmIjoxNzY2NTU0MDAyLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJlNjIxZGFhYS0wYTcwLTRhYzQtODY0Yy1iNmM0OWM4NTU5ODZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImZkN2UxMjgyLWJmZjItNDA2MC1hOGU2LWM5NzA4NDdlNGNiMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC4xMDEsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ5NTQwMDI1MTB9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.IO0WPAsZUCHZM-P892I8O9PcBp-M0EJE7Ms2XoIpH9TNLrJZtHlIGZJhKYZhG0L_3UBEfc3iJzFmSOHv-eAeJQ"
API_SECRET = "GsSB^CXGLBHtRn1*pU$_!tWfre3@I^VK"
EXPIRY     = "2025-12-30"

class EnhancedMarketRecorder:
    def __init__(self):
        print("\n" + "="*70)
        print("📹 ENHANCED MARKET RECORDER v2.0")
        print("   ✓ Change Tracking")
        print("   ✓ OI Analysis")
        print("   ✓ Real-time Alerts")
        print("="*70)
        
        # Initialize Engine
        fut_symbol = self._format_future_symbol(EXPIRY)
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY, fut_symbol)
        
        # Setup files
        date_str = datetime.now().strftime('%Y-%m-%d')
        base_path = "D:\\StockMarket\\StockMarket\\scripts\\claude\\market_recorder"
        os.makedirs(base_path, exist_ok=True)
        
        self.master_file = f"{base_path}\\Master_Data_{date_str}.csv"
        self.alerts_file = f"{base_path}\\Alerts_{date_str}.csv"
        
        # Historical tracking (last 60 seconds)
        self.history = {
            'spot': deque(maxlen=60),
            'ce_price': deque(maxlen=60),
            'pe_price': deque(maxlen=60),
            'ce_oi': deque(maxlen=60),
            'pe_oi': deque(maxlen=60),
            'pcr': deque(maxlen=60)
        }
        
        # Previous tick values
        self.prev = {
            'spot': 0,
            'ce_price': 0,
            'pe_price': 0,
            'ce_oi': 0,
            'pe_oi': 0,
            'pcr': 0
        }
        
        # Statistics
        self.tick_count = 0
        self.start_time = datetime.now()
        self.alerts_triggered = 0
        
        self._init_files()
        
        print(f"\n✅ Recorder Ready")
        print(f"📁 Master File: {self.master_file}")
        print(f"📁 Alerts File: {self.alerts_file}")
        print("="*70 + "\n")
    
    def _format_future_symbol(self, expiry):
        dt = datetime.strptime(expiry, "%Y-%m-%d")
        return f"NSE-NIFTY-{dt.strftime('%d%b%y')}-FUT"
    
    def _init_files(self):
        """Initialize CSV files"""
        # Master Data File - EVERYTHING in ONE place
        if not os.path.exists(self.master_file):
            with open(self.master_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    # Time
                    "Timestamp", "Unix_Time",
                    # Spot Data
                    "Spot", "Spot_Chg", "Spot_Chg_Pct", "Spot_Velocity",
                    "Spot_MA_5sec", "Spot_MA_15sec", "Spot_MA_60sec",
                    # Future Data
                    "Future", "Basis", "Basis_Pct",
                    # Technical Indicators
                    "RSI", "RSI_Signal", "EMA5", "EMA13", "EMA_Cross",
                    "VWAP", "VWAP_Dist", "VWAP_Signal",
                    # ATM Options
                    "ATM_Strike",
                    # CE Data
                    "CE_Symbol", "CE_Price", "CE_Chg", "CE_Chg_Pct",
                    "CE_OI", "CE_OI_Chg", "CE_OI_Chg_Pct",
                    "CE_Delta", "CE_Theta",
                    # PE Data
                    "PE_Symbol", "PE_Price", "PE_Chg", "PE_Chg_Pct",
                    "PE_OI", "PE_OI_Chg", "PE_OI_Chg_Pct",
                    "PE_Delta", "PE_Theta",
                    # Chain Analysis
                    "PCR", "PCR_Chg", "PCR_Signal",
                    "Total_CE_OI", "Total_PE_OI",
                    # Derived Signals
                    "OI_Signal", "Momentum_Signal", "Trade_Signal"
                ])
        
        # Alerts File
        if not os.path.exists(self.alerts_file):
            with open(self.alerts_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Alert_Type", "Severity", 
                    "Description", "Spot", "ATM_Strike", "Action"
                ])
    
    def calculate_moving_average(self, data_queue, periods):
        """Calculate MA from deque"""
        if len(data_queue) < periods:
            return 0
        return sum(list(data_queue)[-periods:]) / periods
    
    def detect_oi_pattern(self, ce_oi_chg, pe_oi_chg, ce_price_chg, pe_price_chg):
        """Detect OI-based patterns"""
        # Short Covering: CE OI falling + Price rising
        if ce_oi_chg < -1000 and ce_price_chg > 0:
            return "SHORT_COVERING"
        
        # Long Unwinding: PE OI falling + Price falling
        if pe_oi_chg < -1000 and pe_price_chg < 0:
            return "LONG_UNWINDING"
        
        # Fresh Long Building: CE OI rising + Price rising
        if ce_oi_chg > 1000 and ce_price_chg > 0:
            return "LONG_BUILDUP"
        
        # Fresh Short Building: PE OI rising + Price falling
        if pe_oi_chg > 1000 and pe_price_chg < 0:
            return "SHORT_BUILDUP"
        
        return "NEUTRAL"
    
    def generate_trade_signal(self, data):
        """Generate actionable trade signal"""
        signals = []
        
        # Bullish conditions
        if (data['RSI'] > 55 and 
            data['Spot'] > data['VWAP'] and 
            data['EMA5'] > data['EMA13'] and
            data['PCR'] > 1.05):
            signals.append("BUY_CE")
        
        # Bearish conditions
        if (data['RSI'] < 45 and 
            data['Spot'] < data['VWAP'] and 
            data['EMA5'] < data['EMA13'] and
            data['PCR'] < 0.95):
            signals.append("BUY_PE")
        
        # Strong momentum
        if abs(data['Spot_Velocity']) > 5:
            if data['Spot_Chg'] > 0:
                signals.append("MOMENTUM_BULLISH")
            else:
                signals.append("MOMENTUM_BEARISH")
        
        return "|".join(signals) if signals else "NEUTRAL"
    
    def check_alerts(self, data):
        """Check for alert conditions"""
        alerts = []
        
        # 1. Extreme RSI
        if data['RSI'] > 75:
            alerts.append(("OVERBOUGHT", "HIGH", f"RSI at {data['RSI']:.0f} - potential reversal"))
        elif data['RSI'] < 25:
            alerts.append(("OVERSOLD", "HIGH", f"RSI at {data['RSI']:.0f} - potential reversal"))
        
        # 2. Large spot movement
        if abs(data['Spot_Chg']) > 50:
            alerts.append(("BIG_MOVE", "HIGH", f"Spot moved {data['Spot_Chg']:.2f} points"))
        
        # 3. Extreme PCR
        if data['PCR'] > 1.5:
            alerts.append(("HIGH_PCR", "MEDIUM", f"PCR at {data['PCR']:.2f} - heavy put buildup"))
        elif data['PCR'] < 0.5:
            alerts.append(("LOW_PCR", "MEDIUM", f"PCR at {data['PCR']:.2f} - heavy call buildup"))
        
        # 4. Massive OI change
        if abs(data['CE_OI_Chg']) > 10000:
            alerts.append(("CE_OI_SPIKE", "MEDIUM", f"CE OI changed by {data['CE_OI_Chg']:,.0f}"))
        if abs(data['PE_OI_Chg']) > 10000:
            alerts.append(("PE_OI_SPIKE", "MEDIUM", f"PE OI changed by {data['PE_OI_Chg']:,.0f}"))
        
        # 5. OI Pattern detected
        if data['OI_Signal'] in ['SHORT_COVERING', 'LONG_UNWINDING']:
            alerts.append(("OI_PATTERN", "HIGH", f"{data['OI_Signal']} detected"))
        
        # Log alerts
        for alert_type, severity, desc in alerts:
            self.log_alert(alert_type, severity, desc, data)
        
        return len(alerts)
    
    def log_alert(self, alert_type, severity, description, data):
        """Log alert to file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine suggested action
        action = "MONITOR"
        if severity == "HIGH":
            if "OVERBOUGHT" in alert_type or "SHORT_COVERING" in description:
                action = "CONSIDER_CE"
            elif "OVERSOLD" in alert_type or "LONG_UNWINDING" in description:
                action = "CONSIDER_PE"
        
        row = [
            timestamp, alert_type, severity,
            description, data['Spot'], data['ATM_Strike'], action
        ]
        
        with open(self.alerts_file, 'a', newline='') as f:
            csv.writer(f).writerow(row)
        
        self.alerts_triggered += 1
        
        # Print alert
        emoji = "🚨" if severity == "HIGH" else "⚠️"
        print(f"\n{emoji} ALERT: {alert_type} - {description}")
    
    def record_tick(self):
        """Record complete market snapshot"""
        self.tick_count += 1
        
        try:
            # Update engine
            self.engine.update()
            
            # Skip if no data
            if self.engine.spot_ltp == 0:
                return
            
            timestamp = datetime.now()
            unix_time = int(timestamp.timestamp())
            
            # Current values
            spot = self.engine.spot_ltp
            ce = self.engine.atm_ce
            pe = self.engine.atm_pe
            
            # Calculate changes
            spot_chg = spot - self.prev['spot'] if self.prev['spot'] > 0 else 0
            spot_chg_pct = (spot_chg / self.prev['spot'] * 100) if self.prev['spot'] > 0 else 0
            spot_velocity = abs(spot_chg)
            
            ce_chg = ce['ltp'] - self.prev['ce_price'] if self.prev['ce_price'] > 0 else 0
            ce_chg_pct = (ce_chg / self.prev['ce_price'] * 100) if self.prev['ce_price'] > 0 else 0
            
            pe_chg = pe['ltp'] - self.prev['pe_price'] if self.prev['pe_price'] > 0 else 0
            pe_chg_pct = (pe_chg / self.prev['pe_price'] * 100) if self.prev['pe_price'] > 0 else 0
            
            ce_oi_chg = ce['oi'] - self.prev['ce_oi'] if self.prev['ce_oi'] > 0 else 0
            ce_oi_chg_pct = (ce_oi_chg / self.prev['ce_oi'] * 100) if self.prev['ce_oi'] > 0 else 0
            
            pe_oi_chg = pe['oi'] - self.prev['pe_oi'] if self.prev['pe_oi'] > 0 else 0
            pe_oi_chg_pct = (pe_oi_chg / self.prev['pe_oi'] * 100) if self.prev['pe_oi'] > 0 else 0
            
            pcr_chg = self.engine.pcr - self.prev['pcr'] if self.prev['pcr'] > 0 else 0
            
            # Update history
            self.history['spot'].append(spot)
            self.history['ce_price'].append(ce['ltp'])
            self.history['pe_price'].append(pe['ltp'])
            self.history['ce_oi'].append(ce['oi'])
            self.history['pe_oi'].append(pe['oi'])
            self.history['pcr'].append(self.engine.pcr)
            
            # Calculate MAs
            ma_5 = self.calculate_moving_average(self.history['spot'], 5)
            ma_15 = self.calculate_moving_average(self.history['spot'], 15)
            ma_60 = self.calculate_moving_average(self.history['spot'], 60)
            
            # Basis
            basis = spot - self.engine.fut_ltp if self.engine.fut_ltp > 0 else 0
            basis_pct = (basis / spot * 100) if spot > 0 else 0
            
            # Signals
            rsi_signal = "OB" if self.engine.rsi > 70 else "OS" if self.engine.rsi < 30 else "N"
            ema_cross = "B" if self.engine.ema5 > self.engine.ema13 else "S"
            vwap_dist = spot - self.engine.vwap if self.engine.vwap > 0 else 0
            vwap_signal = "A" if spot > self.engine.vwap else "B"
            pcr_signal = "B" if self.engine.pcr > 1.1 else "S" if self.engine.pcr < 0.9 else "N"
            
            # OI Pattern
            oi_signal = self.detect_oi_pattern(ce_oi_chg, pe_oi_chg, ce_chg, pe_chg)
            
            # Momentum
            if self.engine.rsi > 60 and spot > self.engine.vwap:
                momentum = "STRONG_BULL"
            elif self.engine.rsi < 40 and spot < self.engine.vwap:
                momentum = "STRONG_BEAR"
            elif spot > self.engine.vwap:
                momentum = "BULL"
            elif spot < self.engine.vwap:
                momentum = "BEAR"
            else:
                momentum = "NEUTRAL"
            
            # Prepare data dict for signals
            data = {
                'Timestamp': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'Spot': spot,
                'Spot_Chg': spot_chg,
                'Spot_Velocity': spot_velocity,
                'RSI': self.engine.rsi,
                'VWAP': self.engine.vwap,
                'EMA5': self.engine.ema5,
                'EMA13': self.engine.ema13,
                'PCR': self.engine.pcr,
                'ATM_Strike': self.engine.atm_strike,
                'CE_OI_Chg': ce_oi_chg,
                'PE_OI_Chg': pe_oi_chg,
                'OI_Signal': oi_signal
            }
            
            # Generate trade signal
            trade_signal = self.generate_trade_signal(data)
            
            # Build row
            row = [
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                unix_time,
                # Spot
                spot, round(spot_chg, 2), round(spot_chg_pct, 3), round(spot_velocity, 2),
                round(ma_5, 2), round(ma_15, 2), round(ma_60, 2),
                # Future
                self.engine.fut_ltp, round(basis, 2), round(basis_pct, 3),
                # Indicators
                int(self.engine.rsi), rsi_signal, 
                round(self.engine.ema5, 2), round(self.engine.ema13, 2), ema_cross,
                round(self.engine.vwap, 2), round(vwap_dist, 2), vwap_signal,
                # ATM
                self.engine.atm_strike,
                # CE
                ce['symbol'], ce['ltp'], round(ce_chg, 2), round(ce_chg_pct, 3),
                ce['oi'], int(ce_oi_chg), round(ce_oi_chg_pct, 3),
                round(ce['delta'], 4), round(ce['theta'], 4),
                # PE
                pe['symbol'], pe['ltp'], round(pe_chg, 2), round(pe_chg_pct, 3),
                pe['oi'], int(pe_oi_chg), round(pe_oi_chg_pct, 3),
                round(pe['delta'], 4), round(pe['theta'], 4),
                # Chain
                self.engine.pcr, round(pcr_chg, 3), pcr_signal,
                0, 0,  # Total OI (would need full chain)
                # Signals
                oi_signal, momentum, trade_signal
            ]
            
            # Write to file
            with open(self.master_file, 'a', newline='') as f:
                csv.writer(f).writerow(row)
            
            # Check for alerts
            self.check_alerts(data)
            
            # Update previous values
            self.prev.update({
                'spot': spot,
                'ce_price': ce['ltp'],
                'pe_price': pe['ltp'],
                'ce_oi': ce['oi'],
                'pe_oi': pe['oi'],
                'pcr': self.engine.pcr
            })
            
            # Print status
            self._print_status(spot_chg, trade_signal)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    def _print_status(self, spot_chg, signal):
        """Print recording status"""
        runtime = (datetime.now() - self.start_time).seconds
        
        # Direction emoji
        direction = "🟢" if spot_chg > 0 else "🔴" if spot_chg < 0 else "⚪"
        
        status = [
            f"{direction} #{self.tick_count}",
            f"{runtime // 60:02d}:{runtime % 60:02d}",
            f"Spot: {self.engine.spot_ltp:.2f} ({spot_chg:+.2f})",
            f"RSI: {int(self.engine.rsi)}",
            f"PCR: {self.engine.pcr:.2f}",
            f"Signal: {signal[:15]}"
        ]
        
        if self.alerts_triggered > 0:
            status.append(f"🚨 Alerts: {self.alerts_triggered}")
        
        print("\r" + " | ".join(status), end='', flush=True)
    
    def run(self):
        """Main loop"""
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
                    print(f"\r⏸️  Market Closed | {now.strftime('%H:%M:%S')}", end='')
                    time.sleep(30)
                    continue
                
                self.record_tick()
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n\n{'='*70}")
            print("🎬 Recording Stopped")
            print(f"{'='*70}")
            print(f"Total Ticks:  {self.tick_count}")
            print(f"Alerts:       {self.alerts_triggered}")
            print(f"Data File:    {self.master_file}")
            print(f"Alert File:   {self.alerts_file}")
            print(f"{'='*70}\n")

if __name__ == "__main__":
    recorder = EnhancedMarketRecorder()
    recorder.run()
