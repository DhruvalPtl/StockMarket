"""
MULTI-STRATEGY BOT v4.0 (Final Architecture)
✅ 4 Parallel Strategies (A, B, C, Live)
✅ Uses 'claude_groww_logger.py' for separate files
✅ Non-Blocking 5-Second Cycle
"""

import time
import sys
from datetime import datetime
from growwapi import GrowwAPI
from claude_groww_data_pipeline import GrowwDataEngine
from claude_groww_logger import GrowwLogger

# ==========================================
# 1. STRATEGY DEFINITIONS
# ==========================================

class BaseStrategy:
    def __init__(self, name):
        self.name = name
        self.position = None # Holds active trade
        self.logger = GrowwLogger(name) # Dedicated Logger

    def process(self, engine):
        """Main decision loop for this strategy"""
        
        # If Flat -> Check Entry
        if self.position is None:
            signal = self.check_entry(engine)
            if signal:
                self.open_position(signal, engine)
        
        # If Position -> Check Exit
        else:
            self.manage_position(engine)

    def open_position(self, signal, engine):
        # Determine price (Paper Trade)
        price = engine.atm_ce['ltp'] if signal == 'BUY_CE' else engine.atm_pe['ltp']
        strike = engine.atm_ce['strike'] if signal == 'BUY_CE' else engine.atm_pe['strike']
        
        if price <= 0: return

        self.position = {
            'type': signal,
            'entry_price': price,
            'strike': strike,
            'start_time': datetime.now(),
            # Save snapshot for analysis
            'debug_spot': engine.spot_ltp,
            'debug_vwap': engine.vwap,
            'debug_rsi': engine.rsi
        }
        print(f"🔵 {self.name}: BUY {signal} @ {price} (Strike {strike})")

    def manage_position(self, engine):
        # 1. Get current price of our strike
        # (Simplified: assume ATM tracking for paper trade)
        current_price = 0
        if self.position['type'] == 'BUY_CE':
            current_price = engine.atm_ce['ltp']
        else:
            current_price = engine.atm_pe['ltp']
        
        # 2. Calculate PnL Points
        pnl_points = current_price - self.position['entry_price']
        
        # 3. Exit Logic (Universal: +20 pts Target, -10 pts SL)
        reason = None
        if pnl_points >= 20: reason = "TARGET"
        elif pnl_points <= -10: reason = "STOP_LOSS"
        
        if reason:
            self.close_position(current_price, pnl_points, reason)

    def close_position(self, exit_price, pnl_points, reason):
        pnl_rupees = pnl_points * 75 # Lot size
        
        print(f"🟣 {self.name}: SELL {reason} | PnL: Rs. {pnl_rupees:.2f}")
        
        # Prepare Data for Logger
        trade_data = self.position.copy()
        trade_data['exit_price'] = exit_price
        trade_data['pnl'] = pnl_rupees
        trade_data['reason'] = reason
        
        # Log to file
        self.logger.log_trade(trade_data)
        
        # Reset
        self.position = None
        
    def check_entry(self, engine):
        return None # Defined in children

# --- STRATEGY LOGIC ---

class StrategyA(BaseStrategy):
    """Trend: EMA Crossover + VWAP"""
    def check_entry(self, engine):
        # Bullish: Spot > EMA5 > EMA13 & Spot > VWAP
        if engine.ema5 > engine.ema13 and engine.spot_ltp > engine.ema5:
            if engine.spot_ltp > engine.vwap:
                return 'BUY_CE'
        # Bearish
        elif engine.ema5 < engine.ema13 and engine.spot_ltp < engine.ema5:
            if engine.spot_ltp < engine.vwap:
                return 'BUY_PE'
        return None

class StrategyB(BaseStrategy):
    """Mean Reversion: VWAP Bounce"""
    def check_entry(self, engine):
        dist = abs(engine.spot_ltp - engine.vwap)
        # Only enter if near VWAP (within 10 pts)
        if dist < 10:
            if engine.rsi < 45 and engine.spot_ltp > engine.vwap: return 'BUY_CE'
            if engine.rsi > 55 and engine.spot_ltp < engine.vwap: return 'BUY_PE'
        return None

class StrategyC(BaseStrategy):
    """Momentum: High RSI Breakout"""
    def check_entry(self, engine):
        if engine.rsi > 60 and engine.spot_ltp > engine.vwap: return 'BUY_CE'
        if engine.rsi < 40 and engine.spot_ltp < engine.vwap: return 'BUY_PE'
        return None

class StrategyLive(BaseStrategy):
    """Original: VWAP + PCR + RSI"""
    def check_entry(self, engine):
        # Bullish
        if engine.spot_ltp > engine.vwap and engine.pcr > 1.0 and engine.rsi > 50:
            return 'BUY_CE'
        # Bearish
        elif engine.spot_ltp < engine.vwap and engine.pcr < 0.8 and engine.rsi < 50:
            return 'BUY_PE'
        return None

# ==========================================
# 2. MAIN CONTROLLER
# ==========================================

class NiftyScalpingBot:
    def __init__(self, api_key, api_secret, expiry_date):
        print("\n" + "="*60)
        print("🚀 MULTI-STRATEGY CONTROLLER v4.0")
        print("   Mode: Parallel Paper Trading")
        print("="*60)
        
        # 1. Setup Engine
        fut_symbol = f"NSE-NIFTY-{datetime.strptime(expiry_date, '%Y-%m-%d').strftime('%d%b%y')}-FUT"
        self.engine = GrowwDataEngine(api_key, api_secret, expiry_date, fut_symbol)
        self.engine.disable_debug()
        
        # 2. Setup Strategies
        self.strategies = [
            StrategyA("Strat_A_Trend"),
            StrategyB("Strat_B_Reversion"),
            StrategyC("Strat_C_Momentum"),
            StrategyLive("Strat_Live_Original")
        ]
        
        print("✅ Strategies Loaded & Loggers Initialized")

    def run(self):
        print("\n⏳ Starting Data Feed (5s Tick)...\n")
        
        while True:
            try:
                # 1. Update Data (Single API Call)
                self.engine.update()
                
                if not self.engine.rsi_warmup_complete:
                    time.sleep(5)
                    continue

                # 2. Feed Data to All Strategies
                for strat in self.strategies:
                    strat.process(self.engine)
                
                # 3. Wait
                time.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Stopped.")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)

# ==========================================
# EXECUTION
# ==========================================

if __name__ == "__main__":
    API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ3OTEyNzAsImlhdCI6MTc2NjM5MTI3MCwibmJmIjoxNzY2MzkxMjcwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIyNzZlNGNhYy0yZTgyLTQzYTUtYjA4Yi03ZmNiYmMzZmIwNzJcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjRlZjFjNjcxLTM4MjMtNDUyYi1iMDAzLWExOGRmMGQxNDEyYlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjY4Yzk6OWQ4NToyNThlOjI2YywxNzIuNzAuMTgzLjE2NCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDc5MTI3MDU2OX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.IH0-H1Ub186gc1ZZkmkTnQaWw9fXlrdYfKMkzCTAd23ReOLdaB6JNuTMylXVW6gBGZv4X6G1t-2NJKjcapq4wg"
    API_SECRET = "6EY2&DYgrhcxa2IBoeG7-il_cNc2UTaS"
    EXPIRY = "2025-12-30"

    bot = NiftyScalpingBot(API_KEY, API_SECRET, EXPIRY)
    bot.run()