"""
BASE STRATEGY
Enhanced abstract base class for all strategies.

Features:
- Market context awareness (regime, bias, time window)
- Re-entry guard (prevents duplicate signals on same candle)
- Confluence scoring integration
- Adaptive parameters based on market state
- Standardized signal format
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Dict, List, Any
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_intelligence.market_context import (
    MarketContext, MarketRegime, MarketBias, TimeWindow, VolatilityState
)


class SignalType(Enum):
    """Types of trading signals."""
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"
    NO_SIGNAL = "NO_SIGNAL"


class SignalStrength(Enum):
    """Signal strength classification."""
    STRONG = "STRONG"       # High confidence, full size
    MODERATE = "MODERATE"   # Medium confidence, normal size
    WEAK = "WEAK"           # Low confidence, reduced size or skip


@dataclass
class StrategySignal: 
    """
    Standardized signal output from strategies.
    Contains all information needed for execution.
    """
    signal_type:  SignalType
    strength: SignalStrength
    reason: str
    
    # Strategy info
    strategy_name: str
    timeframe: str
    
    # Market context at signal time
    regime: str
    bias: str
    
    # Scoring
    base_score: int              # Strategy's own confidence (1-5)
    confluence_factors: List[str]  # What factors aligned
    
    # Suggested parameters (strategy can override defaults)
    suggested_target:  Optional[float] = None
    suggested_stop:  Optional[float] = None
    preferred_strike_offset: int = 0  # 0 = ATM, 50 = OTM1, -50 = ITM1
    
    # Metadata
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'signal':  self.signal_type.value,
            'strength': self.strength.value,
            'reason': self.reason,
            'strategy': self.strategy_name,
            'timeframe': self.timeframe,
            'regime': self.regime,
            'bias': self.bias,
            'score': self.base_score,
            'factors': self.confluence_factors,
            'timestamp': self.timestamp.strftime("%H:%M:%S")
        }


@dataclass
class MarketData:
    """
    Standardized market data passed to strategies.
    Combines price data with calculated indicators.
    """
    # Timestamp
    timestamp: datetime
    
    # Price data
    spot_price: float
    future_price: float
    future_open: float
    future_high: float
    future_low:  float
    future_close: float
    
    # Key levels
    vwap: float
    atm_strike: int
    
    # Indicators
    rsi: float
    ema_5: float
    ema_13: float
    ema_21: float
    ema_50: float
    adx: float
    atr: float
    
    # Derived
    candle_body:  float
    candle_range: float
    is_green_candle: bool
    
    # Order flow
    pcr: float
    ce_oi_change_pct: float
    pe_oi_change_pct: float
    volume_relative:  float
    
    # Convenience properties
    @property
    def price_above_vwap(self) -> bool:
        return self.future_price > self.vwap
    
    @property
    def price_below_vwap(self) -> bool:
        return self.future_price < self.vwap
    
    @property
    def ema_bullish(self) -> bool:
        """EMA 5 > EMA 13 > EMA 21"""
        return self.ema_5 > self.ema_13 > self.ema_21
    
    @property
    def ema_bearish(self) -> bool:
        """EMA 5 < EMA 13 < EMA 21"""
        return self.ema_5 < self.ema_13 < self.ema_21
    
    @property
    def price_above_ema5(self) -> bool:
        return self.spot_price > self.ema_5
    
    @property
    def price_below_ema5(self) -> bool:
        return self.spot_price < self.ema_5
    
    @property
    def strong_candle(self) -> bool:
        """Candle body > 60% of range"""
        if self.candle_range == 0:
            return False
        return self.candle_body / self.candle_range > 0.6
    
    @property
    def rsi_oversold(self) -> bool:
        return self.rsi < 35
    
    @property
    def rsi_overbought(self) -> bool:
        return self.rsi > 65
    
    @property
    def rsi_bullish_momentum(self) -> bool:
        return 55 <= self.rsi <= 75
    
    @property
    def rsi_bearish_momentum(self) -> bool:
        return 25 <= self.rsi <= 45


class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    
    Features:
    - Market context awareness
    - Re-entry prevention
    - Confluence scoring
    - Regime filtering
    - Time window filtering
    """
    
    # Strategy metadata (override in subclasses)
    STRATEGY_NAME = "BaseStrategy"
    STRATEGY_CODE = "BASE"
    
    # Which regimes this strategy works best in
    OPTIMAL_REGIMES:  List[str] = ["TRENDING", "RANGING", "VOLATILE"]
    
    # Which time windows this strategy is active
    ACTIVE_TIME_WINDOWS: List[str] = [
        "OPENING_SESSION", "MORNING_SESSION", "LUNCH_SESSION", "POWER_HOUR"
    ]
    
    # Minimum context score to generate signal
    MIN_CONTEXT_SCORE = 2
    
    def __init__(self, config, timeframe: str = "1minute"):
        self.config = config
        self.timeframe = timeframe
        
        # Re-entry guard
        self.last_signal_timestamp:  Optional[datetime] = None
        self.last_signal_type:  Optional[SignalType] = None
        
        # Cooldown tracking
        self.last_trade_time: Optional[datetime] = None
        self.cooldown_seconds = config.Exit.COOLDOWN_SECONDS
        
        # Signal history for analysis
        self.signal_history: List[StrategySignal] = []
        
        # Previous data for crossover detection
        self.prev_data: Optional[MarketData] = None
        
        # Stats
        self.signals_generated = 0
        self.signals_filtered = 0
    
    @abstractmethod
    def _check_entry_conditions(self, data: MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        """
        Core strategy logic. Must be implemented by subclasses.
        
        Args:
            data:  Current market data
            context: Current market context
            
        Returns:
            Tuple of (SignalType, reason_string, base_score 1-5)
        """
        pass
    
    def check_entry(self, data: MarketData, context: MarketContext) -> Optional[StrategySignal]:
        """
        Main entry point. Applies filters then calls strategy logic.
        
        Args:
            data: Current market data
            context: Current market context
            
        Returns:
            StrategySignal if conditions met, None otherwise
        """
        # 1.Check if strategy should be active in current regime
        if not self._is_regime_allowed(context):
            return None
        
        # 2.Check if strategy should be active in current time window
        if not self._is_time_window_allowed(context):
            return None
        
        # 3.Check re-entry guard
        if not self._is_new_candle(data.timestamp):
            return None
        
        # 4.Check cooldown
        if not self._is_cooldown_complete():
            return None
        
        # 5.Check if market is tradeable
        if not context.is_tradeable():
            return None
        
        # 6.Call strategy-specific logic
        signal_type, reason, base_score = self._check_entry_conditions(data, context)
        
        if signal_type == SignalType.NO_SIGNAL: 
            self.prev_data = data
            return None
        
        # 7.Calculate confluence factors
        confluence_factors = self._get_confluence_factors(data, context, signal_type)
        
        # 8.Determine signal strength
        strength = self._calculate_signal_strength(base_score, len(confluence_factors), context)
        
        # 9.Get suggested parameters
        suggested_target, suggested_stop = self._get_suggested_exits(context)
        
        # 10.Create signal
        signal = StrategySignal(
            signal_type=signal_type,
            strength=strength,
            reason=reason,
            strategy_name=self.STRATEGY_NAME,
            timeframe=self.timeframe,
            regime=context.regime.value,
            bias=context.bias.value,
            base_score=base_score,
            confluence_factors=confluence_factors,
            suggested_target=suggested_target,
            suggested_stop=suggested_stop,
            preferred_strike_offset=self._get_preferred_strike_offset(signal_type, context)
        )
        
        # 11.Mark signal generated
        self._mark_signal_generated(data.timestamp, signal_type)
        self.signal_history.append(signal)
        self.signals_generated += 1
        
        # 12.Store previous data
        self.prev_data = data
        
        return signal
    
    def _is_regime_allowed(self, context:  MarketContext) -> bool:
        """Check if current regime is suitable for this strategy."""
        current_regime = context.get_regime_simple()
        
        if current_regime not in self.OPTIMAL_REGIMES: 
            self.signals_filtered += 1
            return False
        
        return True
    
    def _is_time_window_allowed(self, context: MarketContext) -> bool:
        """Check if current time window is suitable for this strategy."""
        current_window = context.time_window.value
        
        if current_window not in self.ACTIVE_TIME_WINDOWS:
            self.signals_filtered += 1
            return False
        
        return True
    
    def _is_new_candle(self, current_timestamp: datetime) -> bool:
        """Prevents duplicate signals on same candle."""
        if self.last_signal_timestamp is None:
            return True
        
        # Consider same minute as same candle for 1min timeframe
        if self.timeframe == "1minute":
            return current_timestamp.minute != self.last_signal_timestamp.minute
        elif self.timeframe == "5minute": 
            return (current_timestamp - self.last_signal_timestamp).seconds >= 300
        
        return True
    
    def _is_cooldown_complete(self) -> bool:
        """Check if cooldown period has passed since last trade."""
        if self.last_trade_time is None: 
            return True
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def _mark_signal_generated(self, timestamp: datetime, signal_type:  SignalType):
        """Records that a signal was generated."""
        self.last_signal_timestamp = timestamp
        self.last_signal_type = signal_type
    
    def mark_trade_executed(self):
        """Called when a trade is actually executed (for cooldown)."""
        self.last_trade_time = datetime.now()
    
    def _get_confluence_factors(self, data: MarketData, context: MarketContext, 
                                signal_type: SignalType) -> List[str]:
        """
        Identifies which factors align with the signal direction.
        More factors = higher confluence = better signal.
        """
        factors = []
        is_bullish = signal_type == SignalType.BUY_CE
        
        # 1.Regime alignment
        if is_bullish and context.regime == MarketRegime.TRENDING_UP:
            factors.append("REGIME_ALIGNED")
        elif not is_bullish and context.regime == MarketRegime.TRENDING_DOWN: 
            factors.append("REGIME_ALIGNED")
        
        # 2.Bias alignment
        if is_bullish and context.bias in [MarketBias.BULLISH, MarketBias.STRONG_BULLISH]: 
            factors.append("BIAS_ALIGNED")
        elif not is_bullish and context.bias in [MarketBias.BEARISH, MarketBias.STRONG_BEARISH]:
            factors.append("BIAS_ALIGNED")
        
        # 3.VWAP alignment
        if is_bullish and data.price_above_vwap:
            factors.append("ABOVE_VWAP")
        elif not is_bullish and data.price_below_vwap: 
            factors.append("BELOW_VWAP")
        
        # 4.EMA alignment
        if is_bullish and data.ema_bullish:
            factors.append("EMA_BULLISH")
        elif not is_bullish and data.ema_bearish:
            factors.append("EMA_BEARISH")
        
        # 5.RSI alignment
        if is_bullish and data.rsi_bullish_momentum:
            factors.append("RSI_MOMENTUM")
        elif not is_bullish and data.rsi_bearish_momentum: 
            factors.append("RSI_MOMENTUM")
        
        # 6.Order flow alignment
        if is_bullish and context.order_flow.smart_money_direction == "BULLISH": 
            factors.append("ORDER_FLOW")
        elif not is_bullish and context.order_flow.smart_money_direction == "BEARISH":
            factors.append("ORDER_FLOW")
        
        # 7.Volume confirmation
        if context.order_flow.volume_state in ["SPIKE", "HIGH"]:
            factors.append("VOLUME_CONFIRM")
        
        # 8.Futures premium alignment
        if is_bullish and context.future_premium > 50:
            factors.append("PREMIUM_BULLISH")
        elif not is_bullish and context.future_premium < 20:
            factors.append("PREMIUM_BEARISH")
        
        return factors
    
    def _calculate_signal_strength(self, base_score: int, confluence_count: int,
                                   context: MarketContext) -> SignalStrength:
        """
        Determines signal strength based on multiple factors.
        """
        total_score = base_score + confluence_count
        
        # Adjust for volatility
        if context.volatility_state == VolatilityState.HIGH:
            total_score -= 1  # Reduce confidence in high volatility
        elif context.volatility_state == VolatilityState.LOW:
            total_score += 1  # Increase confidence in low volatility
        
        # Adjust for time window
        if context.time_window == TimeWindow.LUNCH_SESSION:
            total_score -= 1  # Reduce confidence during lunch
        elif context.time_window == TimeWindow.POWER_HOUR:
            total_score += 1  # Increase confidence during power hour
        
        # Classify
        if total_score >= 7:
            return SignalStrength.STRONG
        elif total_score >= 4:
            return SignalStrength.MODERATE
        else: 
            return SignalStrength.WEAK
    
    def _get_suggested_exits(self, context: MarketContext) -> Tuple[Optional[float], Optional[float]]:
        """
        Gets regime-adaptive exit parameters.
        """
        exits = context.get_exit_params(self.config)
        return exits.get('target'), exits.get('stop')
    
    def _get_preferred_strike_offset(self, signal_type: SignalType, 
                                     context: MarketContext) -> int:
        """
        Determines preferred strike offset based on conditions.
        
        Returns:
            0 = ATM, 50 = OTM1, 100 = OTM2, -50 = ITM1
        """
        # In high volatility, prefer OTM (cheaper, defined risk)
        if context.volatility_state == VolatilityState.HIGH: 
            return 100 if signal_type == SignalType.BUY_CE else -100
        
        # In low volatility, prefer ATM (higher delta, faster moves)
        if context.volatility_state == VolatilityState.LOW: 
            return 0
        
        # Default to OTM1
        return 50 if signal_type == SignalType.BUY_CE else -50
    
    def get_stats(self) -> Dict[str, Any]: 
        """Returns strategy statistics."""
        return {
            'name': self.STRATEGY_NAME,
            'timeframe': self.timeframe,
            'signals_generated': self.signals_generated,
            'signals_filtered': self.signals_filtered,
            'filter_rate': (self.signals_filtered / 
                          (self.signals_generated + self.signals_filtered) * 100
                          if (self.signals_generated + self.signals_filtered) > 0 else 0)
        }


class DummyStrategy(BaseStrategy):
    """
    Dummy strategy for testing.
    Generates no signals, just validates the framework.
    """
    
    STRATEGY_NAME = "Dummy"
    STRATEGY_CODE = "DUMMY"
    
    def _check_entry_conditions(self, data:  MarketData, context: MarketContext) -> Tuple[SignalType, str, int]:
        return SignalType.NO_SIGNAL, "", 0


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Base Strategy Framework...\n")
    
    # Create mock config
    class MockConfig:
        class Exit:
            COOLDOWN_SECONDS = 60
            DEFAULT_TARGET_POINTS = 12
            DEFAULT_STOP_LOSS_POINTS = 6
            EXITS_BY_REGIME = {
                'TRENDING': {'target': 15, 'stop':  5},
                'RANGING': {'target':  8, 'stop':  8},
                'VOLATILE': {'target':  20, 'stop':  10}
            }
    
    # Create mock data
    from market_intelligence.market_context import MarketContextBuilder, OrderFlowState
    
    data = MarketData(
        timestamp=datetime.now(),
        spot_price=24050,
        future_price=24100,
        future_open=24000,
        future_high=24120,
        future_low=23980,
        future_close=24100,
        vwap=24020,
        atm_strike=24000,
        rsi=62,
        ema_5=24040,
        ema_13=24020,
        ema_21=24000,
        ema_50=23950,
        adx=28,
        atr=45,
        candle_body=80,
        candle_range=140,
        is_green_candle=True,
        pcr=1.15,
        ce_oi_change_pct=3.5,
        pe_oi_change_pct=5.2,
        volume_relative=1.8
    )
    
    context = MarketContextBuilder()\
        .set_regime(MarketRegime.TRENDING_UP, 28, 10)\
        .set_bias(MarketBias.BULLISH, 45)\
        .set_time_window(TimeWindow.MORNING_SESSION, 300, False)\
        .set_volatility(VolatilityState.NORMAL, 45, 55, 50)\
        .set_order_flow(OrderFlowState(
            smart_money_direction="BULLISH",
            volume_state="HIGH"
        ))\
        .build()
    
    # Test dummy strategy
    dummy = DummyStrategy(MockConfig())
    signal = dummy.check_entry(data, context)
    
    print(f"Strategy: {dummy.STRATEGY_NAME}")
    print(f"Signal:  {signal}")
    print(f"Stats: {dummy.get_stats()}")
    
    # Test MarketData properties
    print(f"\nMarketData Properties:")
    print(f"  price_above_vwap: {data.price_above_vwap}")
    print(f"  ema_bullish:  {data.ema_bullish}")
    print(f"  rsi_bullish_momentum: {data.rsi_bullish_momentum}")
    print(f"  strong_candle:  {data.strong_candle}")
    
    print("\n✅ Base Strategy Framework Test Complete!")