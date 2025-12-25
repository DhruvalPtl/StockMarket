import time
from datetime import datetime
from offline_data_pipeline import GrowwDataEngine 
from groww_logger import GrowwLogger

# ===========================
# 🔧 CONFIGURATION
# ===========================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
EXPIRY     = "2025-12-30" 

# STRATEGY CONSTANTS
CAPITAL       = 10000.0
QUANTITY      = 75       # 1 Lot
SL_POINTS     = 8.0      
TRAIL_TRIGGER = 10.0     
TRAIL_LOCK    = 5.0      
GRIND_VELOCITY_LIMIT = 0.8  
WALL_BUFFER          = 15   

class StructuralSniper:
    def __init__(self):
        print("🚀 STARTING V19 SNIPER (Groww Premium Data)...")
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY)
        self.logger = GrowwLogger()
        
        self.in_trade = False
        self.trade = {}
        self.burst_high = 0
        self.burst_low = 0
        self.last_spot = 0
        
    def get_velocity(self):
        if self.last_spot == 0: return 0
        return abs(self.engine.spot_ltp - self.last_spot)

    def run(self):
        print("⏳ Waiting for Market Ticks...")
        while True:
            self.last_spot = self.engine.spot_ltp
            self.engine.update()
            spot = self.engine.spot_ltp
            
            if spot == 0: 
                time.sleep(1); continue

            # 1. MORNING PHASE (Before 10:00 AM)
            if datetime.now().time() < datetime.strptime("10:00", "%H:%M").time():
                if spot > self.burst_high: self.burst_high = spot
                if self.burst_low == 0 or spot < self.burst_low: self.burst_low = spot
                status = "WATCHING"
                reason = "Defining Wall"
            
            # 2. SNIPER PHASE
            elif not self.in_trade:
                velocity = self.get_velocity()
                status = "SCAN"
                reason = "Waiting"
                signal = None

                # LOGIC: Slow Grind + Wall + Delta Divergence
                if velocity > 0 and velocity < GRIND_VELOCITY_LIMIT:
                    
                    # Resistance Wall (High)
                    if spot >= (self.burst_high - WALL_BUFFER):
                        # REAL DELTA CHECK: If CE Delta is weak (< 0.50) despite high price
                        if self.engine.atm_ce['delta'] < 0.50: 
                            signal = "PE"
                            reason = f"Wall Rejection (Delta {self.engine.atm_ce['delta']})"

                    # Support Wall (Low)
                    elif spot <= (self.burst_low + WALL_BUFFER):
                        # REAL DELTA CHECK: If PE Delta is weak (> -0.50)
                        if self.engine.atm_pe['delta'] > -0.50:
                            signal = "CE"
                            reason = f"Wall Support (Delta {self.engine.atm_pe['delta']})"

                if signal:
                    data = self.engine.atm_ce if signal == "CE" else self.engine.atm_pe
                    ltp = data['ltp']
                    if ltp > 0 and (ltp * QUANTITY <= CAPITAL):
                        print(f"\n⚡ LIVE SIGNAL: {signal} @ {ltp} | {reason}")
                        self.in_trade = True
                        self.trade = {
                            'symbol': data['symbol'], 'type': signal, 'entry_price': ltp,
                            'sl': ltp - SL_POINTS, 'peak': ltp, 'entry_time': datetime.now()
                        }
                        status = "ENTRY"

            # 3. TRADE MANAGEMENT
            else:
                status = "HOLD"
                curr_ltp = self.engine.atm_ce['ltp'] if self.trade['type'] == 'CE' else self.engine.atm_pe['ltp']
                profit = curr_ltp - self.trade['entry_price']
                
                # Trail SL
                if curr_ltp > self.trade['peak']: self.trade['peak'] = curr_ltp
                if profit >= TRAIL_TRIGGER: self.trade['sl'] = self.trade['entry_price'] + TRAIL_LOCK

                # Exit
                duration = (datetime.now() - self.trade['entry_time']).seconds
                if curr_ltp <= self.trade['sl'] or duration > 180:
                    pnl = profit * QUANTITY
                    self.logger.log_trade(self.trade, curr_ltp, pnl, CAPITAL + pnl, status)
                    self.in_trade = False
                    status = "EXIT"
                    print(f"🔴 EXIT TRADE | PnL: {pnl:.2f}")

            # 4. LOGGING
            self.logger.log_tick(self.engine, self.get_velocity(), self.burst_high, self.burst_low, status, reason)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Spot: {spot} | Delta: {self.engine.atm_ce['delta']} | {status}   ", end='\r')
            time.sleep(1)

if __name__ == "__main__":
    StructuralSniper().run()