"""
STRATEGY RUNNER MODULE
The 'Brain' that executes trades.
It connects the Strategy Logic (Signal) with the Data Engine (Price) 
and handles Position Management (Target, Stop Loss, Trailing).
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
import time

from config import BotConfig
from enhanced_data_pipeline import GrowwDataEngine
from enhanced_logger import GrowwLogger
from strategies import BaseStrategy

class StrategyConfig:
    """Helper to pass configuration values cleanly."""
    def __init__(self):
        # Risk & Exit
        self.target_points = BotConfig.TARGET_POINTS
        self.stop_loss_points = BotConfig.STOP_LOSS_POINTS
        self.trailing_activation = BotConfig.TRAILING_STOP_ACTIVATION
        self.trailing_distance = BotConfig.TRAILING_STOP_DISTANCE
        self.max_hold_time = BotConfig.MAX_HOLD_TIME_MINUTES
        self.cooldown = BotConfig.COOLDOWN_SECONDS
        
        # Strategy Parameters
        self.RSI_OVERSOLD = BotConfig.RSI_OVERSOLD
        self.RSI_OVERBOUGHT = BotConfig.RSI_OVERBOUGHT
        self.RSI_MOMENTUM_LOW = BotConfig.RSI_MOMENTUM_LOW
        self.RSI_MOMENTUM_HIGH = BotConfig.RSI_MOMENTUM_HIGH
        self.RSI_MOMENTUM_LOW_BEAR = BotConfig.RSI_MOMENTUM_LOW_BEAR
        self.RSI_MOMENTUM_HIGH_BEAR = BotConfig.RSI_MOMENTUM_HIGH_BEAR
        self.MIN_CANDLE_BODY = BotConfig.MIN_CANDLE_BODY

class StrategyRunner:
    """
    Manages the lifecycle of a single strategy on a specific timeframe.
    """
    
    def __init__(self, 
                 strategy_name: str, 
                 timeframe: str,
                 strategy_logic: BaseStrategy, 
                 engine: GrowwDataEngine, 
                 capital: float):
        
        self.strategy_name = strategy_name
        self.timeframe = timeframe
        self.logic = strategy_logic
        self.engine = engine
        self.logger = GrowwLogger(strategy_name, timeframe)
        self.config = StrategyConfig()
        
        # Account State
        self.initial_capital = capital
        self.current_capital = capital
        self.daily_pnl = 0.0
        
        # Position State
        self.active_position: Optional[Dict] = None
        self.last_exit_time: Optional[datetime] = None
        
        # Tracking
        self.trades_today: List[Dict] = []
        self.prev_row_data = None  # To handle crossover logic (Strategy B)

    def _build_row_data(self) -> Dict:
        """Constructs the data packet required by strategies."""
        e = self.engine
        
        # Safety: Ensure VWAP is valid
        vwap = e.vwap if e.vwap > 0 else e.fut_ltp
        
        return {
            'timestamp': e.timestamp, # Crucial for re-entry guard
            'close': e.spot_ltp,
            'fut_close': e.fut_ltp,
            'fut_open': e.fut_open,
            'fut_high': e.fut_high,
            'fut_low': e.fut_low,
            'vwap': vwap,
            'rsi': e.rsi,
            'ema_fast': e.ema5,
            'ema_slow': e.ema13,
            'pcr': e.pcr,
            
            # Pre-calculated Logic Helpers
            'fut_above_vwap': e.fut_ltp > vwap,
            'fut_below_vwap': e.fut_ltp < vwap,
            'ema_bullish': e.ema5 > e.ema13,
            'ema_bearish': e.ema5 < e.ema13,
            'spot_above_ema_fast': e.spot_ltp > e.ema5,
            'spot_below_ema_fast': e.spot_ltp < e.ema5,
            'candle_green': e.candle_green,
            'candle_body': e.candle_body
        }

    def process_tick(self):
        """Main decision loop called by the Orchestrator."""
        
        # 1. Update Position (if active)
        if self.active_position:
            self._manage_position()
            return

        # 2. Check Cooldown
        if self.last_exit_time:
            elapsed = (datetime.now() - self.last_exit_time).total_seconds()
            if elapsed < self.config.cooldown:
                return

        # 3. Check for Entry
        self._check_entry()

    def _check_entry(self):
        """Asks the strategy logic if we should enter."""
        # Need valid data
        if self.engine.spot_ltp == 0: return
        
        current_row = self._build_row_data()
        
        # Get Signal
        signal, reason = self.logic.check_entry(current_row, self.prev_row_data)
        
        # Log Tick (Scanning)
        # Note: We only log distinct events or periodically to avoid spam, 
        # but for debug we log everything.
        self.logger.log_tick(self.engine, signal, self.daily_pnl, reason)
        
        if signal:
            self._place_order(signal, reason)
        
        # Update Previous Row (Deep Copy logic roughly simulated by dict creation)
        self.prev_row_data = current_row

    def _place_order(self, signal: str, reason: str):
        """Executes the entry order (Paper Trading)."""
        option_type = 'CE' if 'CE' in signal else 'PE'
        
        # 1. Money Management
        max_cost = self.current_capital * BotConfig.MAX_CAPITAL_USAGE_PCT
        
        # 2. Select Strike
        option = self.engine.get_affordable_strike(option_type, max_cost)
        
        if not option:
            print(f"⚠️ [{self.strategy_name}] Signal {signal} ignored: No affordable strike.")
            return

        entry_price = option['ltp']
        strike = option['strike']
        symbol = option['symbol']
        
        # 3. Create Position Record
        self.active_position = {
            'symbol': symbol,
            'type': option_type,
            'strike': strike,
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'peak': entry_price,
            'trailing_active': False,
            
            # Exits
            'target': entry_price + self.config.target_points,
            'stop_loss': entry_price - self.config.stop_loss_points
        }
        
        # 4. CRITICAL: Tell Engine to watch this strike! (Issue #2 Fix)
        self.engine.register_active_strike(strike)
        
        print(f"\n🚀 ENTRY [{self.strategy_name}]: {option_type} {strike} @ {entry_price}")

    def _manage_position(self):
        """Monitors active position for exits."""
        pos = self.active_position
        
        # 1. Get Live Price (Robust Fetcher)
        current_price = self.engine.get_option_price(pos['symbol'], pos['strike'], pos['type'])
        
        # Safety: If API fails and returns 0, hold position (don't panic sell)
        if current_price <= 0.1:
            return

        # 2. Update Peak
        if current_price > pos['peak']:
            pos['peak'] = current_price
            
        # 3. Check Exits
        exit_reason = None
        
        # A. Stop Loss
        if current_price <= pos['stop_loss']:
            exit_reason = "STOP_LOSS"
            
        # B. Target
        elif current_price >= pos['target']:
            exit_reason = "TARGET"
            
        # C. Trailing Stop
        else:
            # Check Activation
            profit = current_price - pos['entry_price']
            target_profit = pos['target'] - pos['entry_price']
            
            if not pos['trailing_active']:
                if profit >= (target_profit * self.config.trailing_activation):
                    pos['trailing_active'] = True
                    # print(f"✨ Trailing Activated for {self.strategy_name}")
            
            if pos['trailing_active']:
                # Dynamic Stop: Peak - 15%
                trail_price = pos['peak'] * (1 - self.config.trailing_distance)
                if current_price <= trail_price:
                    exit_reason = "TRAILING_STOP"

        # D. Time Exit
        duration = (datetime.now() - pos['entry_time']).total_seconds() / 60
        if duration >= self.config.max_hold_time:
            exit_reason = "TIME_LIMIT"
            
        # 4. Execute Exit
        if exit_reason:
            self._exit_position(current_price, exit_reason)
        else:
            # Log Monitor status (optional, maybe every 10s)
            pass

    def _exit_position(self, exit_price: float, reason: str):
        """Closes the position and updates records."""
        pos = self.active_position
        
        # 1. Calculate PnL
        points = exit_price - pos['entry_price']
        pnl = points * BotConfig.LOT_SIZE
        
        # 2. Update Account
        self.current_capital += pnl
        self.daily_pnl += pnl
        self.last_exit_time = datetime.now()
        
        # 3. Log
        self.logger.log_trade(pos, exit_price, pnl, self.current_capital, reason)
        self.trades_today.append({'pnl': pnl}) # Minimal record for summary
        
        # 4. CRITICAL: Stop watching strike (Issue #2 Fix)
        self.engine.unregister_active_strike(pos['strike'])
        
        # 5. Clear State
        self.active_position = None
        
    def force_exit(self, reason="FORCE_EXIT"):
        """Forced exit (e.g., End of Day)."""
        if self.active_position:
            pos = self.active_position
            # Try to get price, else use last peak or entry (worst case)
            price = self.engine.get_option_price(pos['symbol'], pos['strike'], pos['type'])
            if price <= 0.1:
                price = pos['entry_price'] # Break even assumption if data missing
            
            self._exit_position(price, reason)

    def get_summary(self) -> Dict:
        """Returns stats for the daily summary."""
        wins = len([t for t in self.trades_today if t['pnl'] > 0])
        return {
            'name': f"{self.strategy_name}",
            'timeframe': self.timeframe,
            'initial': self.initial_capital,
            'final': self.current_capital,
            'pnl': self.current_capital - self.initial_capital,
            'pnl_pct': ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            'trades': len(self.trades_today),
            'wins': wins,
            'losses': len(self.trades_today) - wins,
            'win_rate': (wins / len(self.trades_today) * 100) if self.trades_today else 0.0
        }