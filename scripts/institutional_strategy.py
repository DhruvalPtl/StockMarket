import time
from datetime import datetime
from groww_data_pipeline import GrowwDataEngine
from groww_logger import GrowwLogger

# ===========================
# 🔧 MECHANICAL CONFIGURATION
# ===========================
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ3OTEyNzAsImlhdCI6MTc2NjM5MTI3MCwibmJmIjoxNzY2MzkxMjcwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIyNzZlNGNhYy0yZTgyLTQzYTUtYjA4Yi03ZmNiYmMzZmIwNzJcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjRlZjFjNjcxLTM4MjMtNDUyYi1iMDAzLWExOGRmMGQxNDEyYlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjY4Yzk6OWQ4NToyNThlOjI2YywxNzIuNzAuMTgzLjE2NCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDc5MTI3MDU2OX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.IH0-H1Ub186gc1ZZkmkTnQaWw9fXlrdYfKMkzCTAd23ReOLdaB6JNuTMylXVW6gBGZv4X6G1t-2NJKjcapq4wg"
API_SECRET = "6EY2&DYgrhcxa2IBoeG7-il_cNc2UTaS"
EXPIRY     = "2025-12-30" 

# RISK & SIZE (Strictly for ₹10,000 capital)
CAPITAL       = 10000.0
QUANTITY      = 75       # 1 Lot Nifty
SL_POINTS     = 8.0      # Tight stop for capital protection
TRAIL_TRIGGER = 10.0     
TRAIL_LOCK    = 5.0      
TIME_STAGNATION = 180    # 3-minute exit to avoid Theta decay

# MECHANICAL THRESHOLDS (Physics of Price)
GRIND_VELOCITY_LIMIT = 0.5  # Points per tick (Slow move detection)
WALL_BUFFER          = 15   # Point distance from Morning High/Low to consider it a "Wall"

class StructuralSniper:
    def __init__(self):
        # Initialize Engine & Logger
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY, fut_symbol="NSE-NIFTY-30Dec25-FUT")
        self.logger = GrowwLogger()
        
        # State Tracking
        self.in_trade = False
        self.trade = {}
        self.burst_high = 0
        self.burst_low = 0
        self.last_spot = 0  # FIX: We track this here to avoid the AttributeError
        
    def get_velocity(self):
        """Calculates instantaneous Price Velocity"""
        if self.last_spot == 0: return 0
        return abs(self.engine.spot_ltp - self.last_spot)

    def run(self):
        print("🚀 SNIPER ACTIVE: Watching for Burst -> Grind -> Wall...")
        
        while True:
            # 1. Store previous spot before updating
            self.last_spot = self.engine.spot_ltp
            
            # 2. Fetch fresh data
            self.engine.update()
            spot = self.engine.spot_ltp
            
            if spot == 0: 
                time.sleep(1); continue

            # 3. MORNING PHASE: Define the "Wall" (Before 10:00 AM)
            current_time = datetime.now().time()
            if current_time < datetime.strptime("10:00", "%H:%M").time():
                if spot > self.burst_high: self.burst_high = spot
                if self.burst_low == 0 or spot < self.burst_low: self.burst_low = spot
                status, reason = "WATCHING", "Recording Morning Burst"
            
            # 4. SCANNING PHASE: Searching for Exhaustion
            elif not self.in_trade:
                velocity = self.get_velocity()
                status = "SCANNING"
                reason = "Waiting for Grind to Wall"
                signal = None

                # MECHANICAL TRIGGER: Slow Grind + Near Structural Wall
                if velocity > 0 and velocity < GRIND_VELOCITY_LIMIT:
                    
                    # CASE A: Resistance Wall (Morning High)
                    if spot >= (self.burst_high - WALL_BUFFER):
                        # Confirm with Option Greeks: Delta flattening
                        if self.engine.atm_ce['delta'] < 0.50: 
                            signal = "PE"
                            reason = "Resistance Wall Exhaustion"

                    # CASE B: Support Wall (Morning Low)
                    elif spot <= (self.burst_low + WALL_BUFFER):
                        if self.engine.atm_pe['delta'] > -0.50:
                            signal = "CE"
                            reason = "Support Wall Exhaustion"

                # 5. ENTRY EXECUTION
                if signal:
                    data = self.engine.atm_ce if signal == "CE" else self.engine.atm_pe
                    ltp = data['ltp']
                    
                    if ltp > 0 and (ltp * QUANTITY <= CAPITAL):
                        self.in_trade = True
                        self.trade = {
                            'symbol': data['symbol'], 'type': signal, 'entry_price': ltp,
                            'sl': ltp - SL_POINTS, 'peak': ltp, 'entry_time': datetime.now()
                        }
                        status = "ENTRY"
                        print(f"\n⚡ STRIKE: {signal} @ {ltp} | {reason}")

            # 6. MANAGING PHASE (Stop Loss & Trailing)
            else:
                status = "IN_TRADE"
                curr_ltp = self.engine.atm_ce['ltp'] if self.trade['type'] == 'CE' else self.engine.atm_pe['ltp']
                profit = curr_ltp - self.trade['entry_price']
                
                if curr_ltp > self.trade['peak']: self.trade['peak'] = curr_ltp
                
                # Trailing Logic
                if profit >= TRAIL_TRIGGER: 
                    self.trade['sl'] = self.trade['entry_price'] + TRAIL_LOCK
                
                # Exit Logic (SL or Time-based)
                stagnation_secs = (datetime.now() - self.trade['entry_time']).seconds
                if curr_ltp <= self.trade['sl'] or stagnation_secs > TIME_STAGNATION:
                    pnl = round(profit * QUANTITY, 2)
                    self.logger.log_trade(self.trade, curr_ltp, pnl, CAPITAL + pnl, "Structural Exit")
                    self.in_trade = False
                    status = "EXIT"
                    print(f"\n🔴 EXIT: PnL: {pnl} | Reason: {status}")

            # 7. DASHBOARD LOGGING
            self.logger.log_tick(self.engine, status, 0, reason)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Spot: {spot} | V: {self.get_velocity():.2f} | Wall: {self.burst_high}/{self.burst_low}   ", end='\r')
            time.sleep(1)

if __name__ == "__main__":
    StructuralSniper().run()