"""
GEMINI NIFTY ALGO TRADING BOT - OPTIMIZED VERSION
✅ Dynamic Expiry (Avoids 0DTE on expiry day)
✅ Smart Strike Selection (Falls back to OTM if ATM is too expensive)
✅ Optimized RSI Zones (30-45 Bearish / 55-70 Bullish)
✅ Stagnancy Rule (Tightens Trailing SL after 15 mins)
"""

import time
import sys
from datetime import datetime, timedelta
from growwapi import GrowwAPI
from claude_groww_data_pipeline import GrowwDataEngine
from claude_groww_logger import GrowwLogger


class NiftyScalpingBot:
    def __init__(self, api_key, api_secret, expiry_date, capital=10000):
        print("\n" + "="*60)
        print("🚀 GEMINI NIFTY BOT (OPTIMIZED v3.0)")
        print("="*60)
        
        self.last_exit_time = None
        self.cooldown_seconds = 60
        
        # API Setup
        self.api_key = api_key
        self.api_secret = api_secret
        self.capital = capital
        self.initial_capital = capital
        
        # Risk Management
        self.daily_loss_limit = capital * 0.10
        self.trades_today = []
        self.daily_pnl = 0
        
        # Position Tracking
        self.active_position = None
        self.lot_size = 75
        self.entry_strike = None
        
        # 1. DYNAMIC EXPIRY LOGIC
        # If today is expiry, switch to next week
        self.expiry_date = self._check_and_update_expiry(expiry_date)
        
        # Early Trading Mode
        self.early_trading_mode = True
        self.early_trading_active = False
        
        # 2. OPTIMIZED STRATEGY PARAMETERS
        self.target_points = 20
        self.stop_loss_points = 10
        self.trailing_stop_activation = 0.40  # Activate earlier (40% of target)
        self.trailing_stop_distance = 0.15    # Initial Trail 15%
        
        # Initialize Data Engine
        fut_symbol = f"NSE-NIFTY-{self._format_expiry_symbol(self.expiry_date)}-FUT"
        self.engine = GrowwDataEngine(api_key, api_secret, self.expiry_date, fut_symbol)
        self.engine.disable_debug()
        
        # Initialize Logger
        self.logger = GrowwLogger()
        
        # Connect
        self._connect()
        
        print(f"\n✅ Bot Initialized")
        print(f"💰 Capital: Rs. {self.capital:,.2f}")
        print(f"📅 Trading Expiry: {self.expiry_date}")
        print(f"⚡ Early Trading: Enabled (starts at 9:17 AM)")
        print("="*60 + "\n")
        
        self.logger.print_session_start()
    
    def _check_and_update_expiry(self, provided_expiry):
        """Check if today is expiry and switch to next week if needed"""
        try:
            today = datetime.now().date()
            expiry_dt = datetime.strptime(provided_expiry, "%Y-%m-%d").date()
            
            if today == expiry_dt:
                next_expiry = expiry_dt + timedelta(days=7)
                print(f"⚠️  NOTICE: Today is Expiry Day ({provided_expiry})")
                print(f"🔄 Switching to Next Weekly Expiry: {next_expiry}")
                return next_expiry.strftime("%Y-%m-%d")
            return provided_expiry
        except Exception as e:
            print(f"⚠️ Expiry Check Error: {e}")
            return provided_expiry

    def _format_expiry_symbol(self, expiry_date):
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def _connect(self):
        try:
            token = GrowwAPI.get_access_token(self.api_key, self.api_secret)
            self.groww = GrowwAPI(token)
            print("✅ Connected to Groww API")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            sys.exit(1)
    
    def check_risk_limits(self):
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            print(f"\n🛑 DAILY LOSS LIMIT HIT: Rs. {self.daily_pnl:.2f}")
            print("Bot shutting down...")
            return False
        return True
    
    def analyze_market_conditions(self):
        spot = self.engine.spot_ltp
        vwap = self.engine.vwap
        pcr = self.engine.pcr
        
        if vwap == 0 or spot == 0:
            return 'NEUTRAL'
        
        rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
        
        # --- EARLY TRADING MODE ---
        if not rsi_ready and self.early_trading_mode:
            if not self.early_trading_active:
                self.early_trading_active = True
                print(f"\n⚡ EARLY MODE: VWAP + PCR + Momentum")
            
            bullish = 0
            bearish = 0
            
            if spot > vwap: bullish += 2
            elif spot < vwap: bearish += 2
            
            if pcr > 1.1: bullish += 1
            elif pcr < 0.9: bearish += 1
            
            changes = self.engine.get_changes()
            if changes['spot_change'] > 15: bullish += 1
            elif changes['spot_change'] < -15: bearish += 1
            
            if bullish >= 2: return 'BULLISH'
            elif bearish >= 2: return 'BEARISH'
            else: return 'NEUTRAL'
        
        # --- FULL STRATEGY MODE ---
        else:
            if self.early_trading_active:
                print(f"\n✅ FULL MODE: VWAP + PCR + RSI + EMA")
                self.early_trading_active = False
            
            rsi = self.engine.rsi
            ema5 = self.engine.ema5
            ema13 = self.engine.ema13
            
            bullish = 0
            bearish = 0
            
            if spot > vwap: bullish += 2
            elif spot < vwap: bearish += 2
            
            if ema5 > ema13 and spot > ema5: bullish += 1
            elif ema5 < ema13 and spot < ema5: bearish += 1
            
            # 3. OPTIMIZED RSI CHECK IN ANALYSIS
            if rsi > 55: bullish += 1
            elif rsi < 45: bearish += 1
            
            if pcr > 1.1: bullish += 1
            elif pcr < 0.9: bearish += 1
            
            if bullish >= 3: return 'BULLISH'
            elif bearish >= 3: return 'BEARISH'
            else: return 'NEUTRAL'
    
    def check_entry_conditions(self, market_bias):
        if self.last_exit_time: 
            elapsed = (datetime.now() - self.last_exit_time).seconds
            if elapsed < self.cooldown_seconds: return None
        
        if market_bias == 'NEUTRAL': return None
        
        spot = self.engine.spot_ltp
        vwap = self.engine.vwap
        rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
        
        # EARLY MODE
        if not rsi_ready and self.early_trading_mode:
            if market_bias == 'BULLISH':
                if spot <= vwap: return None
                if self.engine.get_changes()['spot_change'] < -5: return None
                return 'BUY_CE'
            elif market_bias == 'BEARISH': 
                if spot >= vwap: return None
                if self.engine.get_changes()['spot_change'] > 5: return None
                return 'BUY_PE'
        
        # FULL MODE (OPTIMIZED RSI)
        else: 
            rsi = self.engine.rsi
            
            if market_bias == 'BULLISH': 
                if spot <= vwap: return None
                # Optimized Bullish RSI: 55 to 70
                if rsi < 55 or rsi > 70: return None
                return 'BUY_CE'
            
            elif market_bias == 'BEARISH': 
                if spot >= vwap: return None
                # Optimized Bearish RSI: 30 to 45
                if rsi < 30 or rsi > 45: return None
                return 'BUY_PE'
        
        return None
    
    def get_symbol_for_strike(self, strike, option_type):
        """Helper to construct symbol for any strike"""
        dt = datetime.strptime(self.expiry_date, "%Y-%m-%d")
        year = dt.strftime("%y")
        month = dt.strftime("%b").upper()
        return f"NIFTY{year}{month}{int(strike)}{option_type}"

    def get_price_for_symbol(self, symbol):
        """Fetch live price for any symbol directly from API"""
        try:
            key = f"NSE_{symbol}"
            ltp_response = self.groww.get_ltp(
                segment="FNO",
                exchange_trading_symbols=key
            )
            if ltp_response and key in ltp_response:
                return ltp_response[key]
        except Exception:
            pass
        return 0

    def place_order(self, signal):
        """Execute order with SMART STRIKE SELECTION"""
        try:
            # 1. Identify Target
            if signal == 'BUY_CE':
                base_atm = self.engine.atm_ce
                option_type = 'CE'
                offsets = [0, 50, 100]  # ATM, OTM1, OTM2
            else:
                base_atm = self.engine.atm_pe
                option_type = 'PE'
                offsets = [0, -50, -100] # ATM, OTM1, OTM2
            
            atm_strike = base_atm['strike']
            max_budget = self.capital * 0.70
            
            selected_strike = None
            selected_price = 0
            selected_symbol = ""
            
            print(f"\n🔍 SEARCHING FOR AFFORDABLE STRIKE (Max Budget: Rs. {max_budget:.0f})")
            
            # 2. Strike Selection Loop
            for offset in offsets:
                test_strike = atm_strike + offset
                
                # If ATM, use engine data directly
                if offset == 0:
                    price = base_atm['ltp']
                    symbol = base_atm['symbol']
                else:
                    # Construct OTM symbol and fetch price
                    symbol = self.get_symbol_for_strike(test_strike, option_type)
                    price = self.get_price_for_symbol(symbol)
                
                if price <= 0: continue
                
                total_cost = price * self.lot_size
                print(f"   Checking {test_strike} {option_type} @ {price} = Rs. {total_cost:.0f}...", end="")
                
                if total_cost <= max_budget:
                    print(" ✅ AFFORDABLE")
                    selected_strike = test_strike
                    selected_price = price
                    selected_symbol = symbol
                    break
                else:
                    print(" ❌ TOO EXPENSIVE")
            
            if not selected_strike:
                print("⚠️  No affordable strikes found within 100 points range. Skipping trade.")
                return False
            
            # 3. Place Trade
            self.entry_strike = selected_strike
            
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE EXECUTION")
            print(f"{'='*60}")
            
            self.active_position = {
                'symbol': selected_symbol,
                'type': option_type,
                'strike': selected_strike,
                'entry_price': selected_price,
                'entry_time': datetime.now(),
                'order_id': f"PAPER_{datetime.now().strftime('%H%M%S')}",
                'peak': selected_price,
                'target': selected_price + (self.target_points / 2),
                'stop_loss': selected_price - (self.stop_loss_points / 2),
                'trailing_activated': False
            }
            
            print(f"🟢 POSITION OPENED: {option_type} @ {selected_strike}")
            print(f"   Entry: Rs. {selected_price} | Cost: Rs. {selected_price * self.lot_size:.0f}")
            print(f"   Target: {self.active_position['target']:.2f} | SL: {self.active_position['stop_loss']:.2f}")
            print(f"{'='*60}\n")
            return True
        
        except Exception as e:
            print(f"❌ Order Error: {e}")
            return False
    
    def get_current_option_price(self):
        """Get current price for the specific entry strike"""
        if not self.active_position or not self.entry_strike: return 0
        
        # Always fetch fresh price for exact symbol
        return self.get_price_for_symbol(self.active_position['symbol'])
    
    def manage_position(self):
        """Monitor position with STAGNANCY RULE"""
        if not self.active_position: return
        
        current_price = self.get_current_option_price()
        if current_price == 0: return
        
        if current_price > self.active_position['peak']:
            self.active_position['peak'] = current_price
        
        pnl = (current_price - self.active_position['entry_price']) * self.lot_size
        
        # 4. STAGNANCY RULE: Calculate hold time
        hold_time_mins = (datetime.now() - self.active_position['entry_time']).seconds / 60
        
        # Dynamic Trailing Distance
        current_trail_dist = self.trailing_stop_distance
        if hold_time_mins > 15:
            current_trail_dist = 0.05  # Tighten to 5% after 15 mins
            
        exit_reason = None
        
        # Target
        if current_price >= self.active_position['target']:
            exit_reason = "TARGET"
        
        # Stop Loss
        elif current_price <= self.active_position['stop_loss']:
            exit_reason = "STOP_LOSS"
        
        # Trailing Stop
        else:
            entry = self.active_position['entry_price']
            peak = self.active_position['peak']
            target = self.active_position['target']
            
            profit_pct = (current_price - entry) / entry
            target_profit_pct = (target - entry) / entry
            
            # Activate if 40% of target reached
            if profit_pct >= (target_profit_pct * self.trailing_stop_activation):
                if not self.active_position['trailing_activated']:
                    self.active_position['trailing_activated'] = True
                    print(f"\n✅ Trailing Stop Activated! Peak: {peak:.2f}")
                
                trailing_stop = peak * (1 - current_trail_dist)
                
                # Check for exit (and print if stagnancy rule is active)
                if hold_time_mins > 15 and current_price <= trailing_stop:
                    print("⏳ Stagnancy Exit (Trade > 15 mins)")
                    exit_reason = "STAGNANCY_TRAIL"
                elif current_price <= trailing_stop:
                    exit_reason = "TRAILING_STOP"
        
        # Time Exit
        if hold_time_mins > 30:
            exit_reason = "TIME_EXIT"
        
        if exit_reason:
            self.exit_position(current_price, pnl, exit_reason)
    
    def exit_position(self, exit_price, pnl, reason):
        try:
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE EXIT")
            print(f"{'='*60}")
            
            self.capital += pnl
            self.daily_pnl += pnl
            
            trade_record = {**self.active_position, 'pnl': pnl}
            self.trades_today.append(trade_record)
            
            self.logger.log_trade(
                self.active_position, exit_price, pnl, self.capital, reason
            )
            self.last_exit_time = datetime.now()
            self.active_position = None
            self.entry_strike = None
            
            print(f"Reason: {reason}")
            print(f"PnL: Rs. {pnl:.2f}")
            print(f"New Capital: Rs. {self.capital:,.2f}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Exit Error: {e}")

    def run(self):
        print("🤖 Optimized Bot is now LIVE (Paper Trading)\n")
        iteration = 0
        try:
            while True:
                iteration += 1
                now = datetime.now()
                market_start = now.replace(hour=9, minute=15, second=0)
                market_end = now.replace(hour=15, minute=30, second=0)
                
                if not (market_start <= now <= market_end):
                    if iteration % 12 == 0: print(f"⏸️  Market closed. {now.strftime('%H:%M:%S')}")
                    time.sleep(5)
                    continue

                if self.active_position and now >= now.replace(hour=15, minute=25):
                    self.exit_position(self.get_current_option_price(), 0, "EOD_EXIT")
                    continue
                
                self.engine.update()
                
                if not self.check_risk_limits(): break
                
                if not self.active_position:
                    bias = self.analyze_market_conditions()
                    signal = self.check_entry_conditions(bias)
                    if signal: self.place_order(signal)
                    else:
                        rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
                        mode = "EARLY" if not rsi_ready else "FULL"
                        self.logger.log_tick(self.engine, f"SCAN_{bias}_{mode}", self.daily_pnl, "Scanning")
                else:
                    self.manage_position()
                    curr = self.get_current_option_price()
                    self.logger.log_tick(self.engine, "IN_POSITION", 0, f"@{curr:.2f}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n⚠️  Bot stopped by user")

if __name__ == "__main__":
    # CONFIGURATION
    API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTMwMzAsImlhdCI6MTc2NjU1MzAzMCwibmJmIjoxNzY2NTUzMDMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NTc2NzhiMS1mYjQxLTRkZjgtODc5Zi0yMDc3NTI2MTI5YzFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjEwYzcxYzg2LWM2NzYtNDRhMS05N2VmLTc0N2EzYzdmMTM3Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC41MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDk1MzAzMDAwNX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.qfClpvX56UsEn5qeLufKny_uF8ztmx0TA8WL2_FD_pLcv1l7kMkgec8lw997gwqHLXPu6YJPzdn4ECjXUwhYqQ"
    API_SECRET = "84ENDHT5g1DQE86e2k8(Of*s4ukp!Ari"
    EXPIRY_DATE = "2025-12-30"  # This is a Tuesday
    CAPITAL = 10000
    
    bot = NiftyScalpingBot(API_KEY, API_SECRET, EXPIRY_DATE, CAPITAL)
    bot.run()