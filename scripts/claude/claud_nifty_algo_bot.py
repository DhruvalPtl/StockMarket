"""
NIFTY OPTIONS ALGO TRADING BOT v2.1
High Win-Rate Scalping Strategy with OI & PCR Analysis
Capital: ₹10,000 | Timeframe: 5-minute | Risk: 10% max daily loss
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
        print("🚀 NIFTY OPTIONS SCALPING BOT v2.1")
        print("="*60)
        
        # API Setup
        self.api_key = api_key
        self.api_secret = api_secret
        self.capital = capital
        self.initial_capital = capital
        
        # Risk Management
        self.daily_loss_limit = capital * 0.10  # ₹1,000 for ₹10k
        self.max_risk_per_trade = 500  # ₹500 per trade
        self.trades_today = []
        self.daily_pnl = 0
        
        # Position Tracking
        self.active_position = None
        self.lot_size = 75  # Nifty lot size
        
        # Strategy Parameters
        self.target_points = 20  # Target profit in index points
        self.stop_loss_points = 10  # Stop loss in index points
        
        # Initialize Data Engine
        fut_symbol = f"NSE-NIFTY-{self._format_expiry_symbol(expiry_date)}-FUT"
        self.engine = GrowwDataEngine(api_key, api_secret, expiry_date, fut_symbol)
        
        # Initialize Logger
        self.logger = GrowwLogger()
        
        # Connect to Groww API
        self._connect()
        
        print(f"\n✅ Bot Initialized")
        print(f"💰 Capital: Rs. {self.capital:,.2f}")
        print(f"🛡️  Max Daily Loss: Rs. {self.daily_loss_limit:,.2f}")
        print(f"📊 Expiry: {expiry_date}")
        print("="*60 + "\n")
        
        # Print session start
        self.logger.print_session_start()
    
    def _format_expiry_symbol(self, expiry_date):
        """Convert YYYY-MM-DD to 23Dec25 format"""
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
        """Check if daily loss limit has been breached"""
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            print(f"\n🛑 DAILY LOSS LIMIT HIT: Rs. {self.daily_pnl:.2f}")
            print("Bot shutting down for the day...")
            return False
        return True
    
    def analyze_market_conditions(self):
        """
        Analyze market using VWAP, RSI, PCR, and OI
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        # Get latest data
        spot = self.engine.spot_ltp
        vwap = self.engine.vwap
        rsi = self.engine.rsi
        pcr = self.engine.pcr
        ema5 = self.engine.ema5
        ema13 = self.engine.ema13
        
        # Check data validity
        if spot == 0 or vwap == 0:
            return 'NEUTRAL'
        
        bullish_signals = 0
        bearish_signals = 0
        
        # 1. VWAP Analysis (Primary Bias)
        if spot > vwap:
            bullish_signals += 2
        elif spot < vwap:
            bearish_signals += 2
        
        # 2. EMA Analysis (Momentum)
        if ema5 > ema13 and spot > ema5:
            bullish_signals += 1
        elif ema5 < ema13 and spot < ema5:
            bearish_signals += 1
        
        # 3. RSI Analysis (Momentum Strength)
        if rsi > 60:
            bullish_signals += 1
        elif rsi < 40:
            bearish_signals += 1
        
        # 4. PCR Analysis (Sentiment)
        if pcr > 1.1:  # More puts = bullish support
            bullish_signals += 1
        elif pcr < 0.9:  # More calls = bearish resistance
            bearish_signals += 1
        
        # Decision
        if bullish_signals >= 3:
            return 'BULLISH'
        elif bearish_signals >= 3:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def check_entry_conditions(self, market_bias):
        """
        Check if entry conditions are met for scalping
        Returns: 'BUY_CE', 'BUY_PE', or None
        """
        if market_bias == 'NEUTRAL':
            return None
        
        spot = self.engine.spot_ltp
        vwap = self.engine.vwap
        rsi = self.engine.rsi
        
        # BULLISH ENTRY (Buy CE)
        if market_bias == 'BULLISH':
            # Condition 1: Price above VWAP
            if spot <= vwap:
                return None
            
            # Condition 2: RSI in momentum zone
            if rsi < 55:
                return None
            
            # Condition 3: Check OI decay (Short Covering signal)
            ce_oi = self.engine.atm_ce['oi']
            if ce_oi == 0:  # Need OI data
                return None
            
            return 'BUY_CE'
        
        # BEARISH ENTRY (Buy PE)
        elif market_bias == 'BEARISH':
            # Condition 1: Price below VWAP
            if spot >= vwap:
                return None
            
            # Condition 2: RSI in momentum zone
            if rsi > 45:
                return None
            
            # Condition 3: Check OI decay (Long Unwinding signal)
            pe_oi = self.engine.atm_pe['oi']
            if pe_oi == 0:  # Need OI data
                return None
            
            return 'BUY_PE'
        
        return None
    
    def place_order(self, signal):
        """Execute order on Groww - PAPER TRADING MODE"""
        try:
            if signal == 'BUY_CE':
                symbol = self.engine.atm_ce['symbol']
                entry_price = self.engine.atm_ce['ltp']
                option_type = 'CE'
            else:  # BUY_PE
                symbol = self.engine.atm_pe['symbol']
                entry_price = self.engine.atm_pe['ltp']
                option_type = 'PE'
            
            # Check affordability
            total_cost = entry_price * self.lot_size
            if total_cost > self.capital * 0.7:  # Don't use more than 70% capital
                print(f"⚠️  Premium too high: Rs. {entry_price} x {self.lot_size} = Rs. {total_cost}")
                return False
            
            # PAPER TRADING - No real order placed
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE - NO REAL ORDER PLACED")
            print(f"{'='*60}")
            
            # Track position (simulated)
            self.active_position = {
                'symbol': symbol,
                'type': option_type,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'order_id': f"PAPER_{datetime.now().strftime('%H%M%S')}",
                'peak': entry_price,
                'target': entry_price + (self.target_points / 2),  # Premium target
                'stop_loss': entry_price - (self.stop_loss_points / 2)
            }
            
            print(f"🟢 POSITION OPENED: {option_type}")
            print(f"Symbol: {symbol}")
            print(f"Entry: Rs. {entry_price} | Target: Rs. {self.active_position['target']:.2f}")
            print(f"Stop Loss: Rs. {self.active_position['stop_loss']:.2f}")
            print(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            print(f"❌ Order Error: {e}")
            return False
    
    def manage_position(self):
        """Monitor and exit position based on targets/stop-loss"""
        if not self.active_position:
            return
        
        # Get current price
        if self.active_position['type'] == 'CE':
            current_price = self.engine.atm_ce['ltp']
        else:
            current_price = self.engine.atm_pe['ltp']
        
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
        
        # 3. Trailing Stop (50% profit protection)
        elif self.active_position['peak'] > self.active_position['target']:
            trailing_stop = self.active_position['peak'] * 0.9  # Trail 10% below peak
            if current_price <= trailing_stop:
                exit_reason = "TRAILING_STOP"
        
        # 4. Time-based exit (30 minutes max hold)
        hold_time = (datetime.now() - self.active_position['entry_time']).seconds / 60
        if hold_time > 30:
            exit_reason = "TIME_EXIT"
        
        # Execute exit
        if exit_reason:
            self.exit_position(current_price, pnl, exit_reason)
    
    def exit_position(self, exit_price, pnl, reason):
        """Close position and log trade - PAPER TRADING"""
        try:
            print(f"\n{'='*60}")
            print(f"📝 PAPER TRADE EXIT - NO REAL ORDER PLACED")
            print(f"{'='*60}")
            
            # Update capital (simulated)
            self.capital += pnl
            self.daily_pnl += pnl
            
            # Store trade record
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
            
            # Clear position
            self.active_position = None
            
        except Exception as e:
            print(f"❌ Exit Error: {e}")
    
    def run(self):
        """Main trading loop"""
        print("🤖 Bot is now LIVE (Paper Trading Mode)\n")
        print("💡 Tip: Watch the console for real-time updates!\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                # Check market hours (9:15 AM to 3:30 PM)
                now = datetime.now()
                if not (now.hour == 9 and now.minute >= 15) and not (9 < now.hour < 15) and not (now.hour == 15 and now.minute <= 30):
                    if iteration % 12 == 0:  # Print every minute
                        print(f"⏸️  Market closed. Next check: {now.strftime('%H:%M:%S')}")
                    time.sleep(5)
                    continue
                
                # Update market data (this will show live status)
                self.engine.update()
                
                # Check engine health
                health = self.engine.get_health_status()
                if health['data_quality'] == 'POOR' and iteration > 10:
                    print(f"\n⚠️  Poor data quality. Waiting for better data...")
                    time.sleep(10)
                    continue
                
                # Check risk limits
                if not self.check_risk_limits():
                    break
                
                # If no position, look for entry
                if not self.active_position:
                    market_bias = self.analyze_market_conditions()
                    signal = self.check_entry_conditions(market_bias)
                    
                    if signal:
                        self.place_order(signal)
                    else:
                        # Log market state
                        self.logger.log_tick(
                            self.engine,
                            f"SCANNING_{market_bias}",
                            self.daily_pnl,
                            "Waiting for entry"
                        )
                
                # If position active, manage it
                else:
                    self.manage_position()
                    
                    # Log position state
                    if self.active_position:
                        current_price = self.engine.atm_ce['ltp'] if self.active_position['type'] == 'CE' else self.engine.atm_pe['ltp']
                        unrealized_pnl = (current_price - self.active_position['entry_price']) * self.lot_size
                        
                        self.logger.log_tick(
                            self.engine,
                            f"IN_POSITION_{self.active_position['type']}",
                            unrealized_pnl,
                            f"Monitoring @ Rs. {current_price}"
                        )
                
                # Wait 5 seconds before next iteration
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Bot stopped by user")
            if self.active_position:
                print("⚠️  Active position detected! Closing at market price...")
                current_price = self.engine.atm_ce['ltp'] if self.active_position['type'] == 'CE' else self.engine.atm_pe['ltp']
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
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"  # Replace with your secret
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