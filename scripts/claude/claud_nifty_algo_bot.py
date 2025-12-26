"""
NIFTY OPTIONS ALGO TRADING BOT - COMPLETE FIXED VERSION
✅ Early trading (9:17 AM start)
✅ Strike mismatch fixed (tracks same strike for entry/exit)
✅ Improved trailing stop loss
✅ All previous fixes included
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
        print("🚀 NIFTY OPTIONS SCALPING BOT v2.2 (ALL FIXES)")
        print("="*60)
        
        
        
        self.last_exit_time = None
        self.cooldown_seconds = 60  # 1 minute cooldown after exit
        
        # API Setup
        self.api_key = api_key
        self.api_secret = api_secret
        self.capital = capital
        self.initial_capital = capital
        
        # Risk Management
        self.daily_loss_limit = capital * 0.10  # ₹1,000 for ₹10k
        self.max_risk_per_trade = 500
        self.trades_today = []
        self.daily_pnl = 0
        
        # Position Tracking
        self.active_position = None
        self.lot_size = 75
        
        # Strike Tracking (FIXED: Prevent mismatch)
        self.entry_strike = None  # Track which strike we entered
        
        # Early Trading Mode
        self.early_trading_mode = True
        self.early_trading_active = False
        
        # Strategy Parameters
        self.target_points = 20
        self.stop_loss_points = 10
        self.trailing_stop_activation = 0.5  # Activate after 50% of target
        self.trailing_stop_distance = 0.15   # Trail 15% below peak
        
        # Initialize Data Engine
        fut_symbol = f"NSE-NIFTY-{self._format_expiry_symbol(expiry_date)}-FUT"
        self.engine = GrowwDataEngine(api_key, api_secret, expiry_date, fut_symbol)
        
        # Optional: Disable Debug Mode for Production
        self.engine.disable_debug()
        
        # Initialize Logger
        self.logger = GrowwLogger()
        
        # Connect
        self._connect()
        
        print(f"\n✅ Bot Initialized")
        print(f"💰 Capital: Rs. {self.capital:,.2f}")
        print(f"🛡️  Max Daily Loss: Rs. {self.daily_loss_limit:,.2f}")
        print(f"📊 Expiry: {expiry_date}")
        print(f"⚡ Early Trading: Enabled (starts at 9:17 AM)")
        print("="*60 + "\n")
        
        self.logger.print_session_start()
    
    def _format_expiry_symbol(self, expiry_date):
        """Convert YYYY-MM-DD to 30Dec25 format"""
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def _connect(self):
        """Connect to Groww API"""
        try:
            token = GrowwAPI.get_access_token(
                api_key=self.api_key,
                secret=self.api_secret
            )
            self.groww = GrowwAPI(token)
            print("✅ Connected to Groww API")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            sys.exit(1)
    
    def check_risk_limits(self):
        """Check daily loss limit"""
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            print(f"\n🛑 DAILY LOSS LIMIT HIT: Rs. {self.daily_pnl:.2f}")
            print("Bot shutting down for the day...")
            return False
        return True
    
    def analyze_market_conditions(self):
        """
        Analyze market with early trading support
        Early Mode: VWAP + PCR (9:17-9:30)
        Full Mode: VWAP + PCR + RSI + EMA (9:30+)
        """
        
        spot = self.engine.spot_ltp
        vwap = self.engine.vwap
        pcr = self.engine.pcr
        
        # Check VWAP readiness
        if vwap == 0 or spot == 0:
            return 'NEUTRAL'
        
        # Check if RSI ready
        rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
        
        # --- EARLY TRADING MODE (9:17-9:30) ---
        if not rsi_ready and self.early_trading_mode:
            if not self.early_trading_active:
                self.early_trading_active = True
                print(f"\n{'='*60}")
                print("⚡ EARLY TRADING MODE ACTIVATED")
                print("   Strategy: VWAP + PCR + Momentum")
                print("   Full strategy activates when RSI ready...")
                print(f"{'='*60}\n")
            
            bullish_signals = 0
            bearish_signals = 0
            
            # 1. VWAP (Primary)
            if spot > vwap:
                bullish_signals += 2
            elif spot < vwap:
                bearish_signals += 2
            
            # 2. PCR (Sentiment)
            if pcr > 1.1:
                bullish_signals += 1
            elif pcr < 0.9:
                bearish_signals += 1
            
            # 3. Momentum
            changes = self.engine.get_changes()
            if changes['spot_change'] > 15:
                bullish_signals += 1
            elif changes['spot_change'] < -15:
                bearish_signals += 1
            
            # Decision (need 2+ signals in early mode)
            if bullish_signals >= 2:
                return 'BULLISH'
            elif bearish_signals >= 2:
                return 'BEARISH'
            else:
                return 'NEUTRAL'
        
        # --- FULL STRATEGY MODE (9:30+) ---
        else:
            if self.early_trading_active:
                print(f"\n{'='*60}")
                print("✅✅ FULL STRATEGY MODE ACTIVATED")
                print("   Strategy: VWAP + PCR + RSI + EMA")
                print(f"{'='*60}\n")
                self.early_trading_active = False
            
            rsi = self.engine.rsi
            ema5 = self.engine.ema5
            ema13 = self.engine.ema13
            
            bullish_signals = 0
            bearish_signals = 0
            
            # 1. VWAP
            if spot > vwap:
                bullish_signals += 2
            elif spot < vwap:
                bearish_signals += 2
            
            # 2. EMA
            if ema5 > ema13 and spot > ema5:
                bullish_signals += 1
            elif ema5 < ema13 and spot < ema5:
                bearish_signals += 1
            
            # 3. RSI
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1
            
            # 4. PCR
            if pcr > 1.1:
                bullish_signals += 1
            elif pcr < 0.9:
                bearish_signals += 1
            
            # Decision (need 3+ signals in full mode)
            if bullish_signals >= 3:
                return 'BULLISH'
            elif bearish_signals >= 3:
                return 'BEARISH'
            else:
                return 'NEUTRAL'
    
    def check_entry_conditions(self, market_bias):
        """Check entry with early/full mode support"""
        
        # Cooldown check ✅
        if self.last_exit_time: 
            elapsed = (datetime.now() - self.last_exit_time).seconds
            if elapsed < self. cooldown_seconds: 
                return None  # Still in cooldown
        
        if market_bias == 'NEUTRAL': 
            return None
        
        spot = self.engine. spot_ltp
        vwap = self.engine.vwap
        
        # Check if RSI ready
        rsi_ready = self.engine. rsi_warmup_complete and self. engine.candles_processed >= 15
        
        # --- EARLY MODE:  Relaxed entry ---
        if not rsi_ready and self. early_trading_mode:
            
            if market_bias == 'BULLISH':
                if spot <= vwap: 
                    return None
                
                changes = self.engine. get_changes()
                if changes['spot_change'] < -5:
                    return None
                
                if self.engine. atm_ce['oi'] == 0:
                    return None
                
                return 'BUY_CE'
            
            elif market_bias == 'BEARISH': 
                if spot >= vwap:
                    return None
                
                changes = self. engine.get_changes()
                if changes['spot_change'] > 5:
                    return None
                
                if self. engine.atm_pe['oi'] == 0:
                    return None
                
                return 'BUY_PE'
        
        # --- FULL MODE: Strict entry ---
        else: 
            rsi = self.engine.rsi
            
            if market_bias == 'BULLISH': 
                if spot <= vwap: 
                    return None
                
                # ✅ Accept RSI 55-75 for bullish (reject outside this range)
                if rsi < 55 or rsi > 75:
                    return None
                
                if self.engine.atm_ce['oi'] == 0:
                    return None
                
                return 'BUY_CE'
            
            elif market_bias == 'BEARISH': 
                if spot >= vwap: 
                    return None
                
                # ✅ FIXED: Accept RSI 25-45 for bearish (reject outside this range)
                if rsi < 25 or rsi > 45:
                    return None
                
                if self. engine.atm_pe['oi'] == 0:
                    return None
                
                return 'BUY_PE'
        
        return None
    
    def place_order(self, signal):
        """Execute order - PAPER TRADING with strike tracking"""
        try:
            if signal == 'BUY_CE':
                symbol = self.engine.atm_ce['symbol']
                entry_price = self.engine.atm_ce['ltp']
                strike = self.engine.atm_ce['strike']
                option_type = 'CE'
            else:
                symbol = self.engine.atm_pe['symbol']
                entry_price = self.engine.atm_pe['ltp']
                strike = self.engine.atm_pe['strike']
                option_type = 'PE'
            
            # Affordability check
            total_cost = entry_price * self.lot_size
            if total_cost > self.capital * 0.7:
                print(f"⚠️  Premium too high: Rs. {entry_price} x {self.lot_size} = Rs. {total_cost}")
                return False
            
            # CRITICAL: Store entry strike
            self.entry_strike = strike
            
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE - NO REAL ORDER")
            print(f"{'='*60}")
            
            # Track position with STRIKE
            self.active_position = {
                'symbol': symbol,
                'type': option_type,
                'strike': strike,  # Store strike
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'order_id': f"PAPER_{datetime.now().strftime('%H%M%S')}",
                'peak': entry_price,
                'target': entry_price + (self.target_points / 2),
                'stop_loss': entry_price - (self.stop_loss_points / 2),
                'trailing_activated': False
            }
            
            # Show mode
            rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
            mode = "EARLY" if (not rsi_ready and self.early_trading_mode) else "FULL"
            
            print(f"🟢 POSITION OPENED: {option_type} @ Strike {strike} ({mode} MODE)")
            print(f"Symbol: {symbol}")
            print(f"Entry: Rs. {entry_price} | Target: Rs. {self.active_position['target']:.2f}")
            print(f"Stop Loss: Rs. {self.active_position['stop_loss']:.2f}")
            
            if mode == "FULL":
                print(f"RSI: {self.engine.rsi:.1f} | Spot: {self.engine.spot_ltp:.2f} | VWAP: {self.engine.vwap:.2f}")
            else:
                print(f"Spot: {self.engine.spot_ltp:.2f} | VWAP: {self.engine.vwap:.2f} | PCR: {self.engine.pcr}")
            
            print(f"{'='*60}\n")
            
            return True
        
        except Exception as e:
            print(f"❌ Order Error: {e}")
            return False
    
    def get_current_option_price(self):
        """
        Get current price for the SAME strike we entered
        Symbol format: NIFTY25DEC26000CE (Year + Month + Strike + Type)
        """
        if not self.active_position or not self.entry_strike:
            return 0
        
        option_type = self.active_position['type']
        entry_strike = self.entry_strike
        current_atm = self.engine.atm_strike
        
        # CASE 1: Entry strike is still ATM (use cached - fastest)
        if entry_strike == current_atm:
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            else: 
                return self.engine.atm_pe['ltp']
        
        # CASE 2: ATM moved, fetch our entry strike via API
        try: 
            # Build symbol:  NIFTY25DEC26000CE
            dt = datetime.strptime(self.engine.expiry_date, "%Y-%m-%d")
            year = dt.strftime("%y")           # "25"
            month = dt.strftime("%b").upper()  # "DEC"
            symbol = f"NIFTY{year}{month}{int(entry_strike)}{option_type}"
            
            # Fetch price using get_ltp (fastest)
            ltp_response = self.engine.groww.get_ltp(
                segment="FNO",
                exchange_trading_symbols=f"NSE_{symbol}"
            )
            
            key = f"NSE_{symbol}"
            if ltp_response and key in ltp_response:
                price = ltp_response[key]
                if price > 0:
                    return price
            
            # Fallback to ATM
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            return self.engine.atm_pe['ltp']
        
        except Exception as e:
            print(f"⚠️ Price fetch error: {e}")
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            return self.engine.atm_pe['ltp']
    
    def manage_position(self):
        """Monitor position with improved trailing stop"""
        if not self.active_position:
            return
        
        # Get current price for SAME strike we entered
        current_price = self.get_current_option_price()
        
        if current_price == 0:
            return
        
        # Update peak
        if current_price > self.active_position['peak']:
            self.active_position['peak'] = current_price
        
        # Calculate PnL
        pnl = (current_price - self.active_position['entry_price']) * self.lot_size
        
        # Exit conditions
        exit_reason = None
        
        # 1. Target Hit
        if current_price >= self.active_position['target']:
            exit_reason = "TARGET"
        
        # 2. Stop Loss Hit
        elif current_price <= self.active_position['stop_loss']:
            exit_reason = "STOP_LOSS"
        
        # 3. Improved Trailing Stop
        else:
            entry_price = self.active_position['entry_price']
            peak_price = self.active_position['peak']
            target_price = self.active_position['target']
            
            # Calculate profit percentage
            profit_pct = (current_price - entry_price) / entry_price
            target_profit_pct = (target_price - entry_price) / entry_price
            
            # Activate trailing stop after 50% of target reached
            if profit_pct >= (target_profit_pct * self.trailing_stop_activation):
                if not self.active_position['trailing_activated']:
                    self.active_position['trailing_activated'] = True
                    print(f"\n✅ Trailing Stop Activated! Peak: Rs. {peak_price:.2f}")
                
                # Trail 15% below peak
                trailing_stop = peak_price * (1 - self.trailing_stop_distance)
                
                if current_price <= trailing_stop:
                    exit_reason = "TRAILING_STOP"
        
        # 4. Time-based exit (30 minutes max)
        hold_time = (datetime.now() - self.active_position['entry_time']).seconds / 60
        if hold_time > 30:
            exit_reason = "TIME_EXIT"
        
        # Execute exit
        if exit_reason:
            self.exit_position(current_price, pnl, exit_reason)
    
    def exit_position(self, exit_price, pnl, reason):
        """Close position - PAPER TRADING"""
        try:
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE EXIT")
            print(f"{'='*60}")
            
            # Update capital
            self.capital += pnl
            self.daily_pnl += pnl
            
            # Store trade
            trade_record = {**self.active_position, 'pnl': pnl}
            self.trades_today.append(trade_record)
            
            # Log trade
            self.logger.log_trade(
                self.active_position,
                exit_price,
                pnl,
                self.capital,
                reason
            )
            # Record exit time for cooldown
            self.last_exit_time = datetime.now()
            
            # Clear position and strike
            self.active_position = None
            self.entry_strike = None
        
        except Exception as e:
            print(f"❌ Exit Error: {e}")
    
    def run(self):
        """Main trading loop"""
        print("🤖 Bot is now LIVE (Paper Trading Mode)\n")
        
        if self.early_trading_mode:
            print("⚡ EARLY TRADING ENABLED:")
            print("   📊 Phase 1 (9:17 AM): VWAP + PCR Strategy")
            print("   📊 Phase 2 (9:30 AM): Full Strategy with RSI")
            print("   💡 Watch for automatic mode transitions!\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                # Market hours check
                now = datetime.now()
                # Cleaner market hours check
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)

                if not (market_start <= now <= market_end):
                    if iteration % 12 == 0:
                        print(f"⏸️  Market closed.  Time: {now.strftime('%H:%M:%S')}")
                    time.sleep(5)
                    continue
                
                # Update market data
                self.engine.update()
                
                # Add this after engine. update() in run() to see health: 
                print(f"\n{self.engine.get_health_status()}")
                
                # Health check
                health = self.engine.get_health_status()
                if health['data_quality'] == 'POOR' and iteration > 10:
                    print(f"\n⚠️  Poor data quality. Waiting...")
                    time.sleep(10)
                    continue
                
                # Risk limits check
                if not self.check_risk_limits():
                    break
                
                # No position - look for entry
                if not self.active_position:
                    market_bias = self.analyze_market_conditions()
                    signal = self.check_entry_conditions(market_bias)
                    
                    if signal:
                        self.place_order(signal)
                    else:
                        # Log scanning status
                        rsi_ready = self.engine.rsi_warmup_complete and self.engine.candles_processed >= 15
                        mode = "EARLY" if (not rsi_ready and self.early_trading_mode) else "FULL"
                        
                        self.logger.log_tick(
                            self.engine,
                            f"SCANNING_{market_bias}_{mode}",
                            self.daily_pnl,
                            f"Waiting for entry ({mode} mode)"
                        )
                
                # Position active - manage it
                else:
                    self.manage_position()
                    
                    if self.active_position:
                        current_price = self.get_current_option_price()
                        unrealized_pnl = (current_price - self.active_position['entry_price']) * self.lot_size
                        
                        self.logger.log_tick(
                            self.engine,
                            f"IN_POSITION_{self.active_position['type']}@{self.entry_strike}",
                            unrealized_pnl,
                            f"Monitoring @ Rs. {current_price:.2f}"
                        )
                
                # Wait before next iteration
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Bot stopped by user")
            if self.active_position:
                print("⚠️  Active position detected! Closing at market price...")
                current_price = self.get_current_option_price()
                pnl = (current_price - self.active_position['entry_price']) * self.lot_size
                self.exit_position(current_price, pnl, "MANUAL_EXIT")
        
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.logger.print_session_end(
                self.initial_capital,
                self.capital,
                self.trades_today
            )


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Configuration
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    EXPIRY_DATE = "2025-12-30"  # Next weekly expiry (YYYY-MM-DD)
    CAPITAL = 10000
    
    print("\n⚠️  PAPER TRADING MODE - No real orders will be placed!")
    print("This is for testing and development only.\n")
    
    # Initialize and run bot
    bot = NiftyScalpingBot(
        api_key=API_KEY,
        api_secret=API_SECRET,
        expiry_date=EXPIRY_DATE,
        capital=CAPITAL
    )
    
    bot.run()