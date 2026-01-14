"""
STRATEGY RUNNER
Executes individual strategies with full context integration.

Connects: 
- Data Engine (prices, indicators)
- Market Intelligence (regime, bias, order flow)
- Strategy Logic (signal generation)
- Risk Manager (position management)
- Logger (trade recording)
"""

from datetime import datetime
from typing import Dict, Optional, List, Any
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BotConfig
from data.data_engine import DataEngine, StrikeOIData
from strategies.base_strategy import (
    BaseStrategy, MarketData, StrategySignal, SignalType, SignalStrength
)
from market_intelligence.market_context import (
    MarketContext, MarketContextBuilder, MarketRegime, MarketBias,
    TimeWindow, VolatilityState, OrderFlowState, KeyLevel,
    get_current_time_window, get_minutes_to_close
)
from market_intelligence.regime_detector import RegimeDetector, RegimeState
from market_intelligence.bias_calculator import BiasCalculator, BiasState
from market_intelligence.order_flow_tracker import OrderFlowTracker
from market_intelligence.liquidity_mapper import LiquidityMapper
from execution.risk_manager import RiskManager, Position
from loggers.enhanced_logger import FlattradeLogger


class StrategyRunner:
    """
    Manages the lifecycle of a single strategy instance.
    
    Responsibilities:
    1.Build MarketData from DataEngine
    2.Build MarketContext from Intelligence modules
    3.Call strategy logic
    4.Manage active position (entry, monitoring, exit)
    5.Track performance
    """
    
    def __init__(self,
                 strategy:  BaseStrategy,
                 engine: DataEngine,
                 regime_detector: RegimeDetector,
                 bias_calculator: BiasCalculator,
                 order_flow_tracker: OrderFlowTracker,
                 liquidity_mapper: LiquidityMapper,
                 risk_manager: RiskManager,
                 config):
        
        self.strategy = strategy
        self.engine = engine
        self.regime_detector = regime_detector
        self.bias_calculator = bias_calculator
        self.order_flow_tracker = order_flow_tracker
        self.liquidity_mapper = liquidity_mapper
        self.risk_manager = risk_manager
        self.config = config
        
        # Identity
        self.strategy_name = strategy.STRATEGY_NAME
        self.timeframe = engine.timeframe
        
        # Per-strategy logger
        self.logger = FlattradeLogger(self.strategy_name, self.timeframe)
        
        # Position state
        self.active_position:  Optional[Dict] = None
        self.position_id: Optional[str] = None
        
        # Exit parameters
        self.target_price:  float = 0.0
        self.stop_loss_price: float = 0.0
        self.trailing_active: bool = False
        self.peak_price: float = 0.0
        
        # Timing
        self.last_exit_time: Optional[datetime] = None
        self.cooldown_seconds = config.Exit.COOLDOWN_SECONDS
        
        # Performance tracking
        self.trades_today: List[Dict] = []
        self.daily_pnl: float = 0.0
        self.signals_generated: int = 0
        
        # Tick counter
        self.tick_count: int = 0
    
    def process_tick(self) -> Optional[StrategySignal]:
        """
        Main processing loop called by orchestrator.
        
        Returns:
            StrategySignal if generated, None otherwise
        """
        self.tick_count += 1
        
        # 1.Check if engine is ready
        if not self.engine.is_ready():
            return None
        
        # 2.Check for stale data
        if self.engine.is_data_stale():
            if self.tick_count % 10 == 0:  # Log every 10 ticks to avoid spam
                print(f"⚠️ [{self.strategy_name}] Data is stale, skipping tick")
            return None
        
        # 3.Build MarketData
        market_data = self._build_market_data()
        
        # 4.Build MarketContext
        context = self._build_market_context()
        
        # 5.If in position, manage it
        if self.active_position:
            self._manage_position(market_data, context)
            return None
        
        # 6.Check cooldown
        if not self._is_cooldown_complete():
            return None
        
        # 7.Check market hours
        if not context.is_tradeable():
            return None
        
        # 8.Call strategy for signal
        signal = self.strategy.check_entry(market_data, context)
        
        # 9.Log tick (market snapshot) - log after signal generation
        signal_status = signal.signal_type.value if signal else "SCANNING"
        self.logger.log_tick(
            engine=self.engine,
            signal=signal_status,
            daily_pnl=self.daily_pnl,
            reason=signal.reason if signal else ""
        )
        
        if signal:
            self.signals_generated += 1
            return signal
        
        return None
    
    def _build_market_data(self) -> MarketData: 
        """Builds MarketData from DataEngine."""
        e = self.engine
        
        return MarketData(
            timestamp=e.timestamp or datetime.now(),
            spot_price=e.spot_ltp,
            future_price=e.fut_ltp,
            future_open=e.fut_open,
            future_high=e.fut_high,
            future_low=e.fut_low,
            future_close=e.fut_close,
            vwap=e.vwap if e.vwap > 0 else e.fut_ltp,
            atm_strike=e.atm_strike,
            rsi=e.rsi,
            ema_5=e.ema_5,
            ema_13=e.ema_13,
            ema_21=e.ema_21,
            ema_50=e.ema_50,
            adx=e.adx,
            atr=e.atr,
            candle_body=e.candle_body,
            candle_range=e.candle_range,
            is_green_candle=e.is_green_candle,
            pcr=e.pcr,
            ce_oi_change_pct=self._get_oi_change_pct('CE'),
            pe_oi_change_pct=self._get_oi_change_pct('PE'),
            volume_relative=e.volume_relative
        )
    
    def _get_oi_change_pct(self, option_type: str) -> float:
        """Calculates OI change percentage for ATM strike."""
        atm = self.engine.atm_strike
        if atm in self.engine.strikes_data:
            data = self.engine.strikes_data[atm]
            if option_type == 'CE':
                # Require minimum OI threshold and cap at 500%
                if data.ce_oi > 1000:
                    pct = (data.ce_oi_change / data.ce_oi) * 100
                    return min(max(pct, -500), 500)  # Clamp between -500% and +500%
            else: 
                if data.pe_oi > 1000:
                    pct = (data.pe_oi_change / data.pe_oi) * 100
                    return min(max(pct, -500), 500)  # Clamp between -500% and +500%
        return 0.0
    
    def _build_market_context(self) -> MarketContext:
        """Builds MarketContext from Intelligence modules."""
        e = self.engine
        
        # Get regime
        regime_state = self.regime_detector.update(e.fut_high, e.fut_low, e.fut_close)
        
        # Get bias
        bias_state = self.bias_calculator.update(
            e.spot_ltp, e.fut_ltp, e.vwap, e.pcr, e.rsi
        )
        
        # Get order flow
        strike_data = {
            strike: StrikeOIData(
                strike=strike,
                ce_oi=data.ce_oi,
                pe_oi=data.pe_oi,
                ce_oi_change=data.ce_oi_change,
                pe_oi_change=data.pe_oi_change,
                ce_iv=data.ce_iv,
                pe_iv=data.pe_iv
            )
            for strike, data in e.strikes_data.items()
        }
        
        order_flow_state = self.order_flow_tracker.update(
            e.fut_ltp,
            e.total_ce_oi,
            e.total_pe_oi,
            e.current_volume,
            strike_data,
            e.atm_strike
        )
        
        # Get key levels
        option_chain = {
            strike: {'ce_oi':  data.ce_oi, 'pe_oi': data.pe_oi}
            for strike, data in e.strikes_data.items()
        }
        
        key_levels = self.liquidity_mapper.update(
            e.fut_high, e.fut_low, e.fut_close, e.vwap,
            option_chain, e.atm_strike
        )
        
        # Build context
        builder = MarketContextBuilder()
        
        # Regime
        builder.set_regime(
            regime_state.regime,
            regime_state.adx,
            regime_state.regime_duration
        )
        
        # Bias
        builder.set_bias(bias_state.bias, bias_state.score)
        
        # Time
        time_window = get_current_time_window()
        minutes_to_close = get_minutes_to_close()
        is_expiry = self._is_expiry_day()
        builder.set_time_window(time_window, minutes_to_close, is_expiry)
        
        # Volatility
        vol_state = self._get_volatility_state(e.atr, regime_state)
        builder.set_volatility(vol_state, e.atr, regime_state.atr_percentile, e.get_iv_percentile())
        
        # Prices
        builder.set_prices(e.spot_ltp, e.fut_ltp, e.vwap)
        
        # Indicators
        ema_alignment = self._get_ema_alignment()
        builder.set_indicators(ema_alignment, e.rsi, e.adx)
        
        # Key levels
        support = self.liquidity_mapper.get_nearest_support()
        resistance = self.liquidity_mapper.get_nearest_resistance()
        max_pain = self.liquidity_mapper.get_max_pain()
        builder.set_key_levels(key_levels, support, resistance, max_pain, e.atm_strike)
        
        # Order flow
        builder.set_order_flow(order_flow_state)
        
        # Opening range
        or_high, or_low, or_set = self.liquidity_mapper.get_opening_range()
        builder.set_opening_range(or_high, or_low, or_set)
        
        # Recommendations
        recommended = self._get_recommended_strategies(regime_state, bias_state)
        direction = self._get_preferred_direction(bias_state, order_flow_state)
        confidence = self._calculate_confidence(regime_state, bias_state)
        builder.set_recommendations(recommended, [], direction, confidence)
        
        return builder.build()
    
    def _get_volatility_state(self, atr: float, regime_state:  RegimeState) -> VolatilityState:
        """Determines volatility state."""
        if regime_state.atr_percentile > 85:
            return VolatilityState.EXTREME
        elif regime_state.atr_percentile > 70:
            return VolatilityState.HIGH
        elif regime_state.atr_percentile < 30:
            return VolatilityState.LOW
        return VolatilityState.NORMAL
    
    def _get_ema_alignment(self) -> str:
        """Determines EMA alignment."""
        e = self.engine
        if e.ema_5 > e.ema_13 > e.ema_21:
            return "BULLISH"
        elif e.ema_5 < e.ema_13 < e.ema_21:
            return "BEARISH"
        return "MIXED"
    
    def _is_expiry_day(self) -> bool:
        """Checks if today is expiry day."""
        today = datetime.now().strftime("%Y-%m-%d")
        return today == self.config.OPTION_EXPIRY
    
    def _get_recommended_strategies(self, regime:  RegimeState, bias: BiasState) -> List[str]: 
        """Gets recommended strategies for current conditions."""
        regime_simple = "TRENDING" if regime.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN] else (
            "VOLATILE" if regime.regime == MarketRegime.VOLATILE else "RANGING"
        )
        return self.config.STRATEGY_REGIME_RULES.get(regime_simple, [])
    
    def _get_preferred_direction(self, bias:  BiasState, order_flow: OrderFlowState) -> str:
        """Gets preferred trading direction."""
        if bias.bias in [MarketBias.STRONG_BULLISH, MarketBias.BULLISH]:
            return "CE"
        elif bias.bias in [MarketBias.STRONG_BEARISH, MarketBias.BEARISH]: 
            return "PE"
        
        # Use order flow as tiebreaker
        if order_flow.smart_money_direction == "BULLISH": 
            return "CE"
        elif order_flow.smart_money_direction == "BEARISH":
            return "PE"
        
        return "NONE"
    
    def _calculate_confidence(self, regime:  RegimeState, bias: BiasState) -> float:
        """Calculates overall confidence."""
        return (regime.confidence + bias.confidence) / 2
    
    def _is_cooldown_complete(self) -> bool:
        """Checks if cooldown has passed."""
        if self.last_exit_time is None: 
            return True
        elapsed = (datetime.now() - self.last_exit_time).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    # ==================== POSITION MANAGEMENT ====================
    
    def enter_position(self, signal: StrategySignal, size_multiplier: float = 1.0) -> bool:
        """
        Enters a new position based on signal.
        
        Returns:
            True if position entered, False otherwise
        """
        if self.active_position:
            return False
        
        option_type = 'CE' if signal.signal_type == SignalType.BUY_CE else 'PE'
        
        # Get strike
        max_cost = self.config.Risk.CAPITAL_PER_STRATEGY * self.config.Risk.MAX_CAPITAL_USAGE_PCT * size_multiplier
        strike_data = self.engine.get_affordable_strike(option_type, max_cost)
        
        if not strike_data: 
            print(f"⚠️ [{self.strategy_name}] No affordable strike for {option_type}")
            return False
        
        entry_price = strike_data.ce_ltp if option_type == 'CE' else strike_data.pe_ltp
        strike = strike_data.strike
        
        # Minimum ₹10 premium to prevent negative stop-loss prices
        if entry_price <= 10.0:
            print(f"⚠️ [{self.strategy_name}] Premium too low: ₹{entry_price:.2f}")
            return False
        
        # Get exit parameters
        target_pts = signal.suggested_target or self.config.Exit.DEFAULT_TARGET_POINTS
        stop_pts = signal.suggested_stop or self.config.Exit.DEFAULT_STOP_LOSS_POINTS
        
        # Register with risk manager
        self.position_id = self.risk_manager.register_position(
            strategy_name=self.strategy_name,
            timeframe=self.timeframe,
            direction=signal.signal_type,
            strike=strike,
            entry_price=entry_price,
            quantity=self.config.Risk.LOT_SIZE
        )
        
        # Store position locally
        self.active_position = {
            'position_id': self.position_id,
            'symbol': f"NIFTY-{strike}-{option_type}",
            'type': option_type,
            'strike': strike,
            'entry_price':  entry_price,
            'entry_time': datetime.now(),
            'quantity': self.config.Risk.LOT_SIZE,
            'signal':  signal
        }
        
        # Set exit levels
        self.target_price = entry_price + target_pts
        self.stop_loss_price = entry_price - stop_pts
        self.peak_price = entry_price
        self.trailing_active = False
        
        # Register strike for monitoring
        self.engine.register_active_strike(strike)
        
        # Mark strategy
        self.strategy.mark_trade_executed()
        
        print(f"\n🚀 ENTRY [{self.strategy_name}]:  {option_type} {strike} @ ₹{entry_price:.2f}")
        print(f"   Target: ₹{self.target_price:.2f} | SL: ₹{self.stop_loss_price:.2f}")
        
        return True
    
    def _manage_position(self, data: MarketData, context:  MarketContext):
        """Monitors and manages active position."""
        if not self.active_position:
            return
        
        pos = self.active_position
        
        # Get current price
        current_price = self.engine.get_option_price(pos['strike'], pos['type'])
        
        if current_price <= 0.1:
            # Check how long we've been waiting
            time_in_position = (datetime.now() - pos['entry_time']).total_seconds()
            max_wait_seconds = 300  # 5 minutes
            
            if time_in_position > max_wait_seconds:
                # Force exit at entry price (break-even)
                print(f"⚠️ Strike missing for {time_in_position}s - Force exit")
                self._exit_position(pos['entry_price'], "STRIKE_MISSING")
                return
            
            return  # Don't act on zero price
        
        # Update risk manager
        self.risk_manager.update_position(self.position_id, current_price)
        
        # Update peak
        if current_price > self.peak_price:
            self.peak_price = current_price
        
        # Check exits
        exit_reason = None
        
        # Stop loss
        if current_price <= self.stop_loss_price:
            exit_reason = "STOP_LOSS"
        
        # Target
        elif current_price >= self.target_price:
            exit_reason = "TARGET"
        
        # Trailing stop
        else:
            profit = current_price - pos['entry_price']
            target_profit = self.target_price - pos['entry_price']
            
            if not self.trailing_active:
                activation_pct = self.config.Exit.TRAILING_ACTIVATION_PCT
                if profit >= target_profit * activation_pct: 
                    self.trailing_active = True
            
            if self.trailing_active: 
                trail_distance = self.config.Exit.TRAILING_DISTANCE_PCT
                trail_price = self.peak_price * (1 - trail_distance)
                if current_price <= trail_price:
                    exit_reason = "TRAILING_STOP"
        
        # Time exit
        hold_time = (datetime.now() - pos['entry_time']).total_seconds() / 60
        if hold_time >= self.config.Exit.MAX_HOLD_TIME_MINUTES:
            exit_reason = "TIME_LIMIT"
        
        # Force exit check
        if context.time_window == TimeWindow.CLOSING: 
            exit_reason = "EOD_EXIT"
        
        # Execute exit
        if exit_reason:
            self._exit_position(current_price, exit_reason)
    
    def _exit_position(self, exit_price: float, reason: str):
        """Exits the active position."""
        if not self.active_position:
            return
        
        pos = self.active_position
        
        # Close with risk manager
        net_pnl = self.risk_manager.close_position(self.position_id, exit_price)
        
        # Calculate details
        gross_pnl = (exit_price - pos['entry_price']) * pos['quantity']
        pnl_pct = (net_pnl / (pos['entry_price'] * pos['quantity'])) * 100
        
        # Update tracking
        self.daily_pnl += net_pnl
        self.last_exit_time = datetime.now()
        
        # Create trade record for enhanced logger
        trade_record = {
            'Entry_Time': pos['entry_time'],
            'Exit_Time': datetime.now().strftime("%H:%M:%S"),
            'Strategy': self.strategy_name,
            'Timeframe': self.timeframe,
            'Symbol': pos['symbol'],
            'Type': pos['type'],
            'Strike': pos['strike'],
            'Entry_Price': pos['entry_price'],
            'Exit_Price': exit_price,
            'Max_Price': self.peak_price,
            'PnL': net_pnl,
            'Gross_PnL': gross_pnl,
            'PnL_Pct': pnl_pct,
            'Balance': getattr(self.risk_manager, 'available_capital', 0.0),
            'Exit_Reason': reason
        }
        self.trades_today.append(trade_record)
        
        # Log trade to CSV
        self.logger.log_trade(trade_record)
        
        # Cleanup
        self.engine.unregister_active_strike(pos['strike'])
        self.active_position = None
        self.position_id = None
    
    def force_exit(self, reason: str = "FORCE_EXIT"):
        """Forces exit of any active position."""
        if not self.active_position:
            return
        
        pos = self.active_position
        price = self.engine.get_option_price(pos['strike'], pos['type'])
        
        if price <= 0.1:
            # Use worst-case estimate: assume 50% loss with minimum ₹1
            price = max(1.0, pos['entry_price'] * 0.5)
            print(f"⚠️ [{self.strategy_name}] Strike data missing, using worst-case: ₹{price:.2f}")
        
        self._exit_position(price, reason)
    
    # ==================== REPORTING ====================
    
    def get_summary(self) -> Dict[str, Any]: 
        """Returns strategy performance summary."""
        wins = sum(1 for t in self.trades_today if t['PnL'] > 0)
        losses = len(self.trades_today) - wins
        
        return {
            'strategy':  self.strategy_name,
            'timeframe': self.timeframe,
            'trades':  len(self.trades_today),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / len(self.trades_today) * 100) if self.trades_today else 0,
            'daily_pnl': self.daily_pnl,
            'signals':  self.signals_generated,
            'in_position': self.active_position is not None
        }
    
    def has_position(self) -> bool:
        """Returns True if strategy has active position."""
        return self.active_position is not None


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Strategy Runner...\n")
    
    # This would require full setup, so just test imports
    print("✅ Strategy Runner module loaded successfully!")
    print("   - MarketData building")
    print("   - MarketContext building")
    print("   - Position management")
    print("   - Exit logic")