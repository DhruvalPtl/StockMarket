"""
MARKET CONTEXT - Central Intelligence Aggregator
Collects and provides market state information to all strategies.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional, List, Dict, Any
from enum import Enum


class MarketRegime(Enum):
    """Market regime classification."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class MarketBias(Enum):
    """Directional bias."""
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


class TimeWindow(Enum):
    """Trading session windows."""
    PRE_MARKET = "PRE_MARKET"
    OPENING_SESSION = "OPENING_SESSION"      # 9:15 - 9:45
    MORNING_SESSION = "MORNING_SESSION"       # 9:45 - 11:00
    LUNCH_SESSION = "LUNCH_SESSION"           # 11:00 - 14:00
    POWER_HOUR = "POWER_HOUR"                 # 14:00 - 15:20
    CLOSING = "CLOSING"                       # 15:20 - 15:30
    MARKET_CLOSED = "MARKET_CLOSED"


class VolatilityState(Enum):
    """Volatility classification."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass
class KeyLevel:
    """Represents a support/resistance level."""
    price: float
    level_type: str          # 'SUPPORT', 'RESISTANCE', 'PIVOT', 'MAX_PAIN'
    strength: int            # 1-5 (touches/importance)
    source: str              # 'SWING', 'ROUND_NUMBER', 'OI', 'VWAP'
    
    def __repr__(self):
        return f"{self.level_type}@{self.price}(str:{self.strength})"


@dataclass
class OrderFlowState:
    """Order flow analysis state."""
    # OI Data
    total_ce_oi: int = 0
    total_pe_oi: int = 0
    pcr: float = 1.0
    
    # OI Changes
    ce_oi_change: int = 0
    pe_oi_change: int = 0
    ce_oi_change_pct: float = 0.0
    pe_oi_change_pct:  float = 0.0
    
    # Interpretation
    oi_signal: str = "NEUTRAL"       # 'LONG_BUILDUP', 'SHORT_BUILDUP', etc.
    smart_money_direction: str = "NEUTRAL"  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    
    # Volume
    volume_state: str = "NORMAL"     # 'SPIKE', 'DRY', 'NORMAL'
    relative_volume: float = 1.0     # vs average


@dataclass
class MarketContext: 
    """
    Central Market Intelligence Container.
    All strategies receive this object to make informed decisions.
    """
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)
    
    # === REGIME ===
    regime:  MarketRegime = MarketRegime. UNKNOWN
    regime_strength: float = 0.0          # 0-100 (ADX value)
    regime_duration: int = 0              # Candles in current regime
    
    # === BIAS ===
    bias: MarketBias = MarketBias. NEUTRAL
    bias_score: float = 0.0               # -100 to +100
    
    # === TIME ===
    time_window: TimeWindow = TimeWindow. MARKET_CLOSED
    minutes_to_close: int = 0
    is_expiry_day: bool = False
    
    # === VOLATILITY ===
    volatility_state: VolatilityState = VolatilityState.NORMAL
    atr:  float = 0.0
    atr_percentile: float = 50.0          # Where current ATR sits historically
    iv_percentile: float = 50.0           # Implied volatility percentile
    
    # === PRICE DATA ===
    spot_price: float = 0.0
    future_price: float = 0.0
    future_premium: float = 0.0           # Future - Spot
    vwap: float = 0.0
    
    # === TREND INDICATORS ===
    ema_alignment: str = "MIXED"          # 'BULLISH', 'BEARISH', 'MIXED'
    price_vs_vwap: str = "AT"             # 'ABOVE', 'BELOW', 'AT'
    rsi: float = 50.0
    adx: float = 0.0
    
    # === KEY LEVELS ===
    key_levels:  List[KeyLevel] = field(default_factory=list)
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    max_pain_strike:  int = 0
    atm_strike: int = 0
    
    # === ORDER FLOW ===
    order_flow:  OrderFlowState = field(default_factory=OrderFlowState)
    
    # === OPENING RANGE (for ORB strategy) ===
    opening_range_high: float = 0.0
    opening_range_low:  float = 0.0
    opening_range_set: bool = False
    
    # === STRATEGY RECOMMENDATIONS ===
    recommended_strategies: List[str] = field(default_factory=list)
    avoid_strategies: List[str] = field(default_factory=list)
    
    # === TRADE RECOMMENDATIONS ===
    preferred_direction: str = "NONE"     # 'CE', 'PE', 'NONE'
    confidence_score: float = 0.0         # 0-100
    
    def is_tradeable(self) -> bool:
        """Check if market conditions allow trading."""
        # Not tradeable conditions
        if self. time_window == TimeWindow. MARKET_CLOSED: 
            return False
        if self.time_window == TimeWindow. CLOSING:
            return False
        if self.volatility_state == VolatilityState.EXTREME: 
            return False
        return True
    
    def get_regime_simple(self) -> str:
        """Returns simplified regime for strategy mapping."""
        if self.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            return "TRENDING"
        elif self.regime == MarketRegime. VOLATILE:
            return "VOLATILE"
        else:
            return "RANGING"
    
    def is_strategy_allowed(self, strategy_name: str, config) -> bool:
        """
        Check if strategy should run in current market conditions. 
        Uses both regime and time rules.
        """
        # 1. Check regime rules
        regime_simple = self.get_regime_simple()
        allowed_strategies = config.STRATEGY_REGIME_RULES.get(regime_simple, [])
        
        if strategy_name not in allowed_strategies: 
            return False
        
        # 2. Check time rules
        time_rules = config.TimeWindows. STRATEGY_TIME_RULES.get(strategy_name, [])
        if time_rules:
            current_window = self.time_window. value
            if current_window not in time_rules: 
                return False
        
        return True
    
    def get_exit_params(self, config) -> Dict[str, float]:
        """Returns regime-adaptive exit parameters."""
        regime_simple = self. get_regime_simple()
        exits = config.Exit.EXITS_BY_REGIME.get(
            regime_simple,
            {
                'target': config.Exit.DEFAULT_TARGET_POINTS,
                'stop':  config.Exit.DEFAULT_STOP_LOSS_POINTS
            }
        )
        return exits
    
    def get_position_size_multiplier(self) -> float:
        """
        Returns position size multiplier based on conditions.
        1.0 = normal, 0.5 = reduce, 1.5 = increase
        """
        multiplier = 1.0
        
        # Reduce in high volatility
        if self.volatility_state == VolatilityState.HIGH:
            multiplier *= 0.7
        elif self.volatility_state == VolatilityState.LOW:
            multiplier *= 1.2
            
        # Reduce if low confidence
        if self. confidence_score < 50:
            multiplier *= 0.8
            
        # Reduce during lunch (choppy)
        if self.time_window == TimeWindow. LUNCH_SESSION: 
            multiplier *= 0.8
            
        # Increase during power hour with strong trend
        if self. time_window == TimeWindow.POWER_HOUR:
            if self.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                multiplier *= 1.2
        
        # Clamp between 0.5 and 1.5
        return max(0.5, min(1.5, multiplier))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'timestamp': self.timestamp.strftime("%H:%M:%S"),
            'regime':  self.regime.value,
            'regime_strength': round(self.regime_strength, 1),
            'bias': self.bias. value,
            'bias_score': round(self.bias_score, 1),
            'time_window': self.time_window.value,
            'volatility':  self.volatility_state.value,
            'spot':  self.spot_price,
            'future': self.future_price,
            'premium': round(self. future_premium, 1),
            'vwap': round(self.vwap, 1),
            'rsi': round(self.rsi, 1),
            'adx': round(self.adx, 1),
            'pcr': round(self.order_flow.pcr, 2),
            'atm':  self.atm_strike,
            'max_pain':  self.max_pain_strike,
            'confidence': round(self. confidence_score, 1),
            'preferred_direction': self. preferred_direction
        }
    
    def print_summary(self):
        """Prints a formatted summary of market context."""
        regime_icon = {
            MarketRegime. TRENDING_UP: "📈",
            MarketRegime.TRENDING_DOWN: "📉",
            MarketRegime.RANGING: "↔️",
            MarketRegime. VOLATILE: "⚡",
            MarketRegime. UNKNOWN: "❓"
        }
        
        bias_icon = {
            MarketBias.STRONG_BULLISH: "🟢🟢",
            MarketBias.BULLISH: "🟢",
            MarketBias.NEUTRAL:  "⚪",
            MarketBias. BEARISH: "🔴",
            MarketBias. STRONG_BEARISH: "🔴🔴"
        }
        
        print(f"\n{'='*50}")
        print(f"🧠 MARKET CONTEXT @ {self.timestamp. strftime('%H:%M:%S')}")
        print(f"{'='*50}")
        print(f"Regime:      {regime_icon.get(self.regime, '')} {self.regime.value} (ADX:{self.regime_strength:. 0f})")
        print(f"Bias:       {bias_icon. get(self.bias, '')} {self.bias.value} (Score:{self. bias_score: +.0f})")
        print(f"Window:     {self. time_window.value}")
        print(f"Volatility:  {self.volatility_state.value} (ATR:{self.atr:.1f})")
        print(f"{'─'*50}")
        print(f"Spot:        {self.spot_price:. 2f}")
        print(f"Future:     {self. future_price:.2f} (Premium:{self. future_premium: +.1f})")
        print(f"VWAP:       {self.vwap:. 2f} ({self.price_vs_vwap})")
        print(f"RSI:        {self.rsi:.1f}")
        print(f"{'─'*50}")
        print(f"PCR:        {self.order_flow. pcr:.2f}")
        print(f"OI Signal:  {self. order_flow. oi_signal}")
        print(f"ATM:         {self.atm_strike} | Max Pain: {self. max_pain_strike}")
        print(f"{'─'*50}")
        print(f"Direction:  {self. preferred_direction} (Confidence:{self.confidence_score:. 0f}%)")
        print(f"Strategies: {', '.join(self. recommended_strategies[: 3]) if self.recommended_strategies else 'None'}")
        print(f"{'='*50}\n")


class MarketContextBuilder:
    """
    Builder pattern for constructing MarketContext. 
    Called by the intelligence modules to build the context step by step.
    """
    
    def __init__(self):
        self.context = MarketContext()
    
    def set_timestamp(self, ts: datetime) -> 'MarketContextBuilder':
        self.context.timestamp = ts
        return self
    
    def set_regime(self, regime: MarketRegime, strength: float, duration: int) -> 'MarketContextBuilder':
        self.context.regime = regime
        self.context.regime_strength = strength
        self.context.regime_duration = duration
        return self
    
    def set_bias(self, bias: MarketBias, score: float) -> 'MarketContextBuilder':
        self.context.bias = bias
        self.context.bias_score = score
        return self
    
    def set_time_window(self, window: TimeWindow, minutes_to_close: int, is_expiry:  bool) -> 'MarketContextBuilder':
        self.context.time_window = window
        self.context. minutes_to_close = minutes_to_close
        self. context.is_expiry_day = is_expiry
        return self
    
    def set_volatility(self, state: VolatilityState, atr: float, atr_pct: float, iv_pct:  float) -> 'MarketContextBuilder': 
        self.context.volatility_state = state
        self.context.atr = atr
        self.context.atr_percentile = atr_pct
        self.context.iv_percentile = iv_pct
        return self
    
    def set_prices(self, spot:  float, future: float, vwap: float) -> 'MarketContextBuilder':
        self.context.spot_price = spot
        self.context. future_price = future
        self.context.future_premium = future - spot
        self.context.vwap = vwap
        
        # Derive price vs VWAP
        if vwap > 0:
            diff = spot - vwap
            if diff > 10: 
                self.context. price_vs_vwap = "ABOVE"
            elif diff < -10:
                self.context.price_vs_vwap = "BELOW"
            else:
                self.context.price_vs_vwap = "AT"
        
        return self
    
    def set_indicators(self, ema_alignment: str, rsi: float, adx: float) -> 'MarketContextBuilder':
        self.context. ema_alignment = ema_alignment
        self.context.rsi = rsi
        self.context. adx = adx
        return self
    
    def set_key_levels(self, levels: List[KeyLevel], support: float, resistance:  float, 
                       max_pain: int, atm:  int) -> 'MarketContextBuilder': 
        self.context.key_levels = levels
        self. context.nearest_support = support
        self.context.nearest_resistance = resistance
        self.context.max_pain_strike = max_pain
        self.context.atm_strike = atm
        return self
    
    def set_order_flow(self, flow: OrderFlowState) -> 'MarketContextBuilder': 
        self.context. order_flow = flow
        return self
    
    def set_opening_range(self, high: float, low:  float, is_set: bool) -> 'MarketContextBuilder':
        self. context.opening_range_high = high
        self.context. opening_range_low = low
        self.context.opening_range_set = is_set
        return self
    
    def set_recommendations(self, strategies:  List[str], avoid: List[str], 
                           direction: str, confidence: float) -> 'MarketContextBuilder':
        self.context.recommended_strategies = strategies
        self.context.avoid_strategies = avoid
        self.context. preferred_direction = direction
        self.context.confidence_score = confidence
        return self
    
    def build(self) -> MarketContext: 
        """Returns the built context."""
        return self.context


# ============================================================
# TIME WINDOW HELPER
# ============================================================

def get_current_time_window() -> TimeWindow: 
    """Determines current trading time window."""
    now = datetime.now().time()
    
    # Pre-market
    if now < time(9, 15):
        return TimeWindow.PRE_MARKET
    
    # Opening session:  9:15 - 9:45
    if time(9, 15) <= now < time(9, 45):
        return TimeWindow.OPENING_SESSION
    
    # Morning session: 9:45 - 11:00
    if time(9, 45) <= now < time(11, 0):
        return TimeWindow.MORNING_SESSION
    
    # Lunch session: 11:00 - 14:00
    if time(11, 0) <= now < time(14, 0):
        return TimeWindow.LUNCH_SESSION
    
    # Power hour: 14:00 - 15:20
    if time(14, 0) <= now < time(15, 20):
        return TimeWindow. POWER_HOUR
    
    # Closing:  15:20 - 15:30
    if time(15, 20) <= now <= time(15, 30):
        return TimeWindow.CLOSING
    
    # Market closed
    return TimeWindow.MARKET_CLOSED


def get_minutes_to_close() -> int:
    """Returns minutes until market close (15:30)."""
    now = datetime.now()
    close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if now >= close: 
        return 0
    
    delta = close - now
    return int(delta.total_seconds() / 60)