"""
MULTI-STRATEGY NIFTY OPTIONS ALGO BOT v3.0
✅ Original strategy preserved as "ORIGINAL"
✅ Strategy A: VWAP + EMA Crossover
✅ Strategy B: VWAP Bounce
✅ Strategy C: Momentum Breakout
✅ All 4 strategies run independently and simultaneously
✅ Separate logging per strategy
✅ Performance comparison at end
"""

import time
import sys
from datetime import datetime, timedelta
from growwapi import GrowwAPI
from claude_groww_data_pipeline import GrowwDataEngine
from claude_groww_logger import GrowwLogger, MultiStrategyLogger
from strategies import StrategyA, StrategyB, StrategyC


# ============================================================
# STRATEGY CONFIGURATION
# ============================================================

class StrategyConfig:
    """Shared config for all strategies""" 
    # RSI thresholds
    rsi_oversold = 40
    rsi_overbought = 60
    
    # Momentum thresholds for Strategy C
    rsi_momentum_low = 50
    rsi_momentum_high = 70
    rsi_momentum_low_bear = 30
    rsi_momentum_high_bear = 50
    min_candle_body = 10
    
    # Exit parameters
    target_points = 20
    stop_loss_points = 10
    trailing_stop_activation = 0.5
    trailing_stop_distance = 0.15


# ============================================================
# BASE STRATEGY RUNNER
# ============================================================

class StrategyRunner:
    """Base class for running a single strategy"""
    
    def __init__(self, strategy_name, strategy_obj, engine, config, capital=10000):
        self.strategy_name = strategy_name
        self.strategy = strategy_obj
        self.engine = engine
        self.config = config
        
        # Capital
        self.capital = capital
        self.initial_capital = capital
        self.daily_pnl = 0
        
        # Position tracking
        self.active_position = None
        self.entry_strike = None
        self.lot_size = 75
        
        # Trades
        self.trades_today = []
        
        # Cooldown
        self.last_exit_time = None
        self.cooldown_seconds = 60
        
        # Logger
        self.logger = GrowwLogger(strategy_name)
        
        # Previous row for Strategy B
        self.prev_row = None
    
    def _build_row_data(self):
        """Build current row data for strategy analysis"""
        e = self.engine
        
        row = {
            # Price data
            'close': e.spot_ltp,
            'fut_close': e.fut_ltp,
            'fut_open': e.fut_open,
            'fut_high': e.fut_high,
            'fut_low': e.fut_low,
            
            # Indicators
            'vwap': e.vwap,
            'rsi': e.rsi,
            'ema_fast': e.ema5,
            'ema_slow': e.ema13,
            
            # Derived indicators
            'fut_above_vwap': e.fut_ltp > e.vwap if e.vwap > 0 else False,
            'fut_below_vwap': e.fut_ltp < e.vwap if e.vwap > 0 else False,
            'ema_bullish': e.ema5 > e.ema13 if e.ema13 > 0 else False,
            'ema_bearish': e.ema5 < e.ema13 if e.ema13 > 0 else False,
            'spot_above_ema_fast': e.spot_ltp > e.ema5 if e.ema5 > 0 else False,
            'spot_below_ema_fast': e.spot_ltp < e.ema5 if e.ema5 > 0 else False,
            
            # Candle patterns
            'candle_body': e.candle_body,
            'candle_green': e.candle_green,
            
            # Previous state
            'prev_fut_above_vwap': e.prev_fut_above_vwap
        }
        
        return row
    
    def check_entry(self):
        """Check if entry conditions are met"""
        # Cooldown check
        if self.last_exit_time:
            elapsed = (datetime.now() - self.last_exit_time).seconds
            if elapsed < self.cooldown_seconds:
                return None
        
        # Build current row
        current_row = self._build_row_data()
        
        # Check strategy entry
        signal = self.strategy.check_entry(current_row, self.prev_row)
        
        # Update previous row
        self.prev_row = current_row.copy()
        
        return signal
    
    def place_order(self, signal):
        """Execute order - PAPER TRADING"""
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
                return False
            
            # Store entry strike
            self.entry_strike = strike
            
            # Track position
            self.active_position = {
                'symbol': symbol,
                'type': option_type,
                'strike': strike,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'order_id': f"PAPER_{datetime.now().strftime('%H%M%S')}",
                'peak': entry_price,
                'target': entry_price + (self.config.target_points / 2),
                'stop_loss': entry_price - (self.config.stop_loss_points / 2),
                'trailing_activated': False
            }
            
            print(f"\n[{self.strategy_name}] 🟢 ENTRY: {option_type} @ {strike} | Rs.{entry_price:.2f}")
            
            return True
        
        except Exception as e:
            print(f"\n[{self.strategy_name}] ❌ Order Error: {e}")
            return False
    
    def get_current_option_price(self):
        """Get current price for the strike we entered"""
        if not self.active_position or not self.entry_strike:
            return 0
        
        option_type = self.active_position['type']
        entry_strike = self.entry_strike
        current_atm = self.engine.atm_strike
        
        # If still ATM, use cached
        if entry_strike == current_atm:
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            else:
                return self.engine.atm_pe['ltp']
        
        # Fetch via API
        try:
            dt = datetime.strptime(self.engine.expiry_date, "%Y-%m-%d")
            year = dt.strftime("%y")
            month = dt.strftime("%b").upper()
            symbol = f"NIFTY{year}{month}{int(entry_strike)}{option_type}"
            
            ltp_response = self.engine.groww.get_ltp(
                segment="FNO",
                exchange_trading_symbols=f"NSE_{symbol}"
            )
            
            key = f"NSE_{symbol}"
            if ltp_response and key in ltp_response:
                price = ltp_response[key]
                if price > 0:
                    return price
            
            # Fallback
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            return self.engine.atm_pe['ltp']
        
        except Exception as e:
            if option_type == 'CE':
                return self.engine.atm_ce['ltp']
            return self.engine.atm_pe['ltp']
    
    def manage_position(self):
        """Monitor and exit position"""
        if not self.active_position:
            return
        
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
        
        # 1. Target
        if current_price >= self.active_position['target']:
            exit_reason = "TARGET"
        
        # 2. Stop Loss
        elif current_price <= self.active_position['stop_loss']:
            exit_reason = "STOP_LOSS"
        
        # 3. Trailing Stop
        else:
            entry_price = self.active_position['entry_price']
            peak_price = self.active_position['peak']
            target_price = self.active_position['target']
            
            profit_pct = (current_price - entry_price) / entry_price
            target_profit_pct = (target_price - entry_price) / entry_price
            
            if profit_pct >= (target_profit_pct * self.config.trailing_stop_activation):
                if not self.active_position['trailing_activated']:
                    self.active_position['trailing_activated'] = True
                
                trailing_stop = peak_price * (1 - self.config.trailing_stop_distance)
                
                if current_price <= trailing_stop:
                    exit_reason = "TRAILING_STOP"
        
        # 4. Time exit
        hold_time = (datetime.now() - self.active_position['entry_time']).seconds / 60
        if hold_time > 30:
            exit_reason = "TIME_EXIT"
        
        if exit_reason:
            self.exit_position(current_price, pnl, exit_reason)
    
    def exit_position(self, exit_price, pnl, reason):
        """Close position"""
        try:
            # Update capital
            self.capital += pnl
            self.daily_pnl += pnl
            
            # Store trade
            trade_record = {**self.active_position, 'pnl': pnl}
            self.trades_today.append(trade_record)
            
            # Log
            self.logger.log_trade(
                self.active_position,
                exit_price,
                pnl,
                self.capital,
                reason
            )
            
            # Record exit time
            self.last_exit_time = datetime.now()
            
            # Clear
            self.active_position = None
            self.entry_strike = None
        
        except Exception as e:
            print(f"\n[{self.strategy_name}] ❌ Exit Error: {e}")
    
    def get_unrealized_pnl(self):
        """Get unrealized PnL for active position"""
        if not self.active_position:
            return 0
        
        current_price = self.get_current_option_price()
        return (current_price - self.active_position['entry_price']) * self.lot_size


# ============================================================
# ORIGINAL STRATEGY (from existing bot)
# ============================================================

class OriginalStrategy:
    """The original strategy from the working bot"""
    
    def __init__(self, config):
        self.config = config
        self.name = "ORIGINAL"
        self.early_trading_mode = True
        self.early_trading_active = False
    
    def check_entry(self, row, prev_row=None):
        """Original bot entry logic"""
        # This is the exact logic from analyze_market_conditions + check_entry_conditions
        
        spot = row['close']
        vwap = row['vwap']
        pcr = row.get('pcr', 0)  # Will be added
        rsi = row['rsi']
        
        if vwap == 0 or spot == 0:
            return None
        
        # Check if RSI ready (simplified - will be checked externally)
        rsi_ready = rsi != 50  # If RSI is not default 50, it's calculated
        
        # Market bias analysis
        if not rsi_ready and self.early_trading_mode:
            # Early mode
            bullish_signals = 0
            bearish_signals = 0
            
            if spot > vwap:
                bullish_signals += 2
            elif spot < vwap:
                bearish_signals += 2
            
            if pcr > 1.1:
                bullish_signals += 1
            elif pcr < 0.9:
                bearish_signals += 1
            
            # Momentum check (simplified)
            if row.get('candle_green', False):
                bullish_signals += 1
            else:
                bearish_signals += 1
            
            if bullish_signals >= 2:
                market_bias = 'BULLISH'
            elif bearish_signals >= 2:
                market_bias = 'BEARISH'
            else:
                return None
        else:
            # Full mode
            ema5 = row['ema_fast']
            ema13 = row['ema_slow']
            
            bullish_signals = 0
            bearish_signals = 0
            
            if spot > vwap:
                bullish_signals += 2
            elif spot < vwap:
                bearish_signals += 2
            
            if ema5 > ema13 and spot > ema5:
                bullish_signals += 1
            elif ema5 < ema13 and spot < ema5:
                bearish_signals += 1
            
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1
            
            if pcr > 1.1:
                bullish_signals += 1
            elif pcr < 0.9:
                bearish_signals += 1
            
            if bullish_signals >= 3:
                market_bias = 'BULLISH'
            elif bearish_signals >= 3:
                market_bias = 'BEARISH'
            else:
                return None
        
        # Entry conditions
        if market_bias == 'BULLISH':
            if not rsi_ready:
                # Early mode entry
                if spot > vwap:
                    return 'BUY_CE'
            else:
                # Full mode entry
                if spot > vwap and 55 <= rsi <= 75:
                    return 'BUY_CE'
        
        elif market_bias == 'BEARISH':
            if not rsi_ready:
                # Early mode entry
                if spot < vwap:
                    return 'BUY_PE'
            else:
                # Full mode entry
                if spot < vwap and 25 <= rsi <= 45:
                    return 'BUY_PE'
        
        return None


class OriginalStrategyRunner(StrategyRunner):
    """Runner for original strategy with PCR support"""
    
    def _build_row_data(self):
        """Build row data with PCR"""
        row = super()._build_row_data()
        row['pcr'] = self.engine.pcr
        return row


# ============================================================
# MULTI-STRATEGY BOT
# ============================================================

class MultiStrategyBot:
    def __init__(self, api_key, api_secret, expiry_date, capital=10000):
        print("\n" + "="*80)
        print("🚀 MULTI-STRATEGY NIFTY OPTIONS BOT v3.0")
        print("="*80)
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.capital = capital
        
        # Initialize shared data engine
        fut_symbol = f"NSE-NIFTY-{self._format_expiry_symbol(expiry_date)}-FUT"
        self.engine = GrowwDataEngine(api_key, api_secret, expiry_date, fut_symbol)
        self.engine.disable_debug()
        
        # Initialize config
        config = StrategyConfig()
        
        # Initialize all 4 strategies
        self.strategies = []
        
        # 1. Original Strategy
        original_strat = OriginalStrategy(config)
        original_runner = OriginalStrategyRunner("ORIGINAL", original_strat, self.engine, config, capital)
        self.strategies.append(original_runner)
        
        # 2. Strategy A
        strategy_a = StrategyA(config)
        runner_a = StrategyRunner("STRATEGY_A", strategy_a, self.engine, config, capital)
        self.strategies.append(runner_a)
        
        # 3. Strategy B
        strategy_b = StrategyB(config)
        runner_b = StrategyRunner("STRATEGY_B", strategy_b, self.engine, config, capital)
        self.strategies.append(runner_b)
        
        # 4. Strategy C
        strategy_c = StrategyC(config)
        runner_c = StrategyRunner("STRATEGY_C", strategy_c, self.engine, config, capital)
        self.strategies.append(runner_c)
        
        # Multi-strategy logger
        self.multi_logger = MultiStrategyLogger()
        
        print(f"\n✅ Bot Initialized with {len(self.strategies)} strategies")
        print(f"💰 Capital per strategy: Rs.{capital:,.2f}")
        print(f"📊 Expiry: {expiry_date}")
        print("="*80 + "\n")
    
    def _format_expiry_symbol(self, expiry_date):
        """Convert YYYY-MM-DD to 30Dec25 format"""
        dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        return dt.strftime("%d%b%y")
    
    def run(self):
        """Main trading loop - all strategies run in parallel"""
        print("🤖 Multi-Strategy Bot is now LIVE (Paper Trading)\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                # Market hours check
                now = datetime.now()
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
                
                if not (market_start <= now <= market_end):
                    if iteration % 12 == 0:
                        print(f"⏸️ Market closed. Time: {now.strftime('%H:%M:%S')}")
                    time.sleep(5)
                    continue
                
                # No new entries after 15:20
                no_new_entry_time = now.replace(hour=15, minute=20, second=0)
                force_exit_time = now.replace(hour=15, minute=25, second=0)
                
                # Update shared data engine
                self.engine.update()
                
                # Check data quality
                health = self.engine.get_health_status()
                if health['data_quality'] == 'POOR' and iteration > 10:
                    time.sleep(10)
                    continue
                
                # Force exit all positions at 15:25
                if now >= force_exit_time:
                    for strategy in self.strategies:
                        if strategy.active_position:
                            current_price = strategy.get_current_option_price()
                            pnl = (current_price - strategy.active_position['entry_price']) * strategy.lot_size
                            strategy.exit_position(current_price, pnl, "EOD_EXIT")
                    continue
                
                # Process each strategy independently
                for strategy in self.strategies:
                    # No position - look for entry
                    if not strategy.active_position:
                        # No new entries after 15:20
                        if now >= no_new_entry_time:
                            continue
                        
                        signal = strategy.check_entry()
                        
                        if signal:
                            strategy.place_order(signal)
                        else:
                            # Log scanning
                            strategy.logger.log_tick(
                                self.engine,
                                "SCANNING",
                                strategy.daily_pnl,
                                "Waiting for entry"
                            )
                    
                    # Position active - manage it
                    else:
                        strategy.manage_position()
                        
                        if strategy.active_position:
                            unrealized_pnl = strategy.get_unrealized_pnl()
                            current_price = strategy.get_current_option_price()
                            
                            strategy.logger.log_tick(
                                self.engine,
                                f"IN_POSITION_{strategy.active_position['type']}",
                                unrealized_pnl,
                                f"Monitoring @ Rs.{current_price:.2f}"
                            )
                
                # Print consolidated status every 30 seconds
                if iteration % 6 == 0:
                    self._print_status()
                
                # Wait
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Bot stopped by user")
            
            # Close all open positions
            for strategy in self.strategies:
                if strategy.active_position:
                    print(f"⚠️ Closing {strategy.strategy_name} position...")
                    current_price = strategy.get_current_option_price()
                    pnl = (current_price - strategy.active_position['entry_price']) * strategy.lot_size
                    strategy.exit_position(current_price, pnl, "MANUAL_EXIT")
        
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self._print_final_results()
    
    def _print_status(self):
        """Print consolidated status of all strategies"""
        print(f"\n{'='*80}")
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} | Nifty: {self.engine.spot_ltp:.2f} | "
              f"VWAP: {self.engine.vwap:.2f} | RSI: {self.engine.rsi:.1f}")
        print(f"{'-'*80}")
        
        for strategy in self.strategies:
            status = "IN TRADE" if strategy.active_position else "SCANNING"
            pnl = strategy.daily_pnl + (strategy.get_unrealized_pnl() if strategy.active_position else 0)
            
            print(f"{strategy.strategy_name:<15} | {status:<12} | "
                  f"PnL: Rs.{pnl:>8,.2f} | "
                  f"Trades: {len(strategy.trades_today)}")
        
        print(f"{'='*80}\n")
    
    def _print_final_results(self):
        """Print final comparison and save summary"""
        print("\n\n")
        
        results = []
        
        for strategy in self.strategies:
            # Print individual summary
            strategy.logger.print_session_end(
                strategy.initial_capital,
                strategy.capital,
                strategy.trades_today
            )
            
            # Log to multi-strategy summary
            self.multi_logger.log_strategy_summary(
                strategy.strategy_name,
                strategy.initial_capital,
                strategy.capital,
                strategy.trades_today
            )
            
            # Collect for comparison
            pnl = strategy.capital - strategy.initial_capital
            pnl_pct = (pnl / strategy.initial_capital) * 100
            win_count = sum(1 for t in strategy.trades_today if t.get('pnl', 0) > 0)
            win_rate = (win_count / len(strategy.trades_today) * 100) if strategy.trades_today else 0
            
            avg_win = sum(t['pnl'] for t in strategy.trades_today if t['pnl'] > 0) / win_count if win_count > 0 else 0
            loss_count = len(strategy.trades_today) - win_count
            avg_loss = sum(t['pnl'] for t in strategy.trades_today if t['pnl'] < 0) / loss_count if loss_count > 0 else 0
            
            if avg_loss != 0 and loss_count > 0:
                profit_factor = abs((avg_win * win_count) / (abs(avg_loss) * loss_count))
            else:
                profit_factor = 999.99
            
            results.append({
                'name': strategy.strategy_name,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'trades': len(strategy.trades_today),
                'win_rate': win_rate,
                'profit_factor': profit_factor
            })
        
        # Print comparison
        self.multi_logger.print_final_comparison(results)


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Configuration
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    EXPIRY_DATE = "2025-12-30"
    CAPITAL = 10000  # Per strategy
    
    print("\n⚠️ PAPER TRADING MODE - No real orders!\n")
    
    # Initialize and run multi-strategy bot
    bot = MultiStrategyBot(
        api_key=API_KEY,
        api_secret=API_SECRET,
        expiry_date=EXPIRY_DATE,
        capital=CAPITAL
    )
    
    bot.run()
