"""
REGIME DETECTOR
Determines current market state:  TRENDING, RANGING, or VOLATILE.

Uses: 
- ADX (Average Directional Index) for trend strength
- ATR (Average True Range) for volatility
- Price structure (Higher Highs/Lower Lows) for trend direction

This helps strategies know WHEN to trade, not just WHAT to trade.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple, List
from datetime import datetime

# Import from our package
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_intelligence.market_context import MarketRegime


@dataclass
class RegimeState:
    """Holds current regime analysis results."""
    regime: MarketRegime
    adx:  float
    plus_di: float
    minus_di: float
    atr: float
    atr_percentile: float
    trend_direction: str  # 'UP', 'DOWN', 'NONE'
    regime_duration: int  # Candles in current regime
    confidence: float     # 0-100


class RegimeDetector:
    """
    Detects market regime using ADX, ATR, and price structure.
    
    Regimes: 
    - TRENDING_UP: ADX > 25, +DI > -DI, Higher Highs
    - TRENDING_DOWN: ADX > 25, -DI > +DI, Lower Lows
    - RANGING: ADX < 20, price oscillating
    - VOLATILE:  ATR spike > 1.5x normal
    """
    
    def __init__(self, config):
        self.config = config
        
        # ADX settings
        self.adx_period = 14
        self.adx_trending = config.Regime.ADX_TRENDING_THRESHOLD
        self.adx_ranging = config.Regime.ADX_RANGING_THRESHOLD
        
        # ATR settings
        self.atr_period = config.Regime.ATR_PERIOD
        self.atr_volatile_mult = config.Regime.ATR_VOLATILE_MULTIPLIER
        self.atr_low_mult = config.Regime.ATR_LOW_VOL_MULTIPLIER
        
        # Data storage
        self.highs = deque(maxlen=100)
        self.lows = deque(maxlen=100)
        self.closes = deque(maxlen=100)
        
        # ADX components
        self.tr_values = deque(maxlen=100)
        self.plus_dm = deque(maxlen=100)
        self.minus_dm = deque(maxlen=100)
        
        # ATR history for percentile
        self.atr_history = deque(maxlen=200)
        
        # Regime tracking
        self.current_regime = MarketRegime.UNKNOWN
        self.regime_start_index = 0
        self.candle_count = 0
        
        # Swing point tracking
        self.swing_highs = deque(maxlen=20)
        self.swing_lows = deque(maxlen=20)
        
        # Warmup flag
        self.is_warmed_up = False

    def update(self, high: float, low:  float, close: float) -> RegimeState:
        """
        Main update method. Call with each new candle.
        
        Args:
            high:  Candle high price
            low:  Candle low price
            close: Candle close price
            
        Returns: 
            RegimeState with current analysis
        """
        self.candle_count += 1
        
        # Store prices
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        # Calculate True Range
        tr = self._calculate_true_range(high, low, close)
        self.tr_values.append(tr)
        
        # Calculate Directional Movement
        plus_dm, minus_dm = self._calculate_directional_movement(high, low)
        self.plus_dm.append(plus_dm)
        self.minus_dm.append(minus_dm)
        
        # Update swing points
        self._update_swing_points()
        
        # Check warmup
        if len(self.closes) < self.adx_period + 5:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                adx=0, plus_di=0, minus_di=0,
                atr=0, atr_percentile=50,
                trend_direction='NONE',
                regime_duration=0,
                confidence=0
            )
        
        self.is_warmed_up = True
        
        # Calculate indicators
        adx, plus_di, minus_di = self._calculate_adx()
        atr = self._calculate_atr()
        atr_percentile = self._calculate_atr_percentile(atr)
        
        # regime_detector.py (after Line 140)
        if self.candle_count % 50 == 0:
            print(f"[Regime] ATR={atr:.1f} ({atr_percentile:.0f}th percentile)")
    
        # Store ATR for history
        self.atr_history.append(atr)
        
        # Determine trend direction from DI
        trend_direction = self._get_trend_direction(plus_di, minus_di)
        
        # Detect regime
        new_regime = self._detect_regime(adx, atr, atr_percentile, plus_di, minus_di)
        
        # Track regime duration
        if new_regime != self.current_regime:
            self.current_regime = new_regime
            self.regime_start_index = self.candle_count
        
        regime_duration = self.candle_count - self.regime_start_index
        
        # Calculate confidence
        confidence = self._calculate_confidence(adx, atr_percentile, regime_duration)
        
        return RegimeState(
            regime=new_regime,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            atr=atr,
            atr_percentile=atr_percentile,
            trend_direction=trend_direction,
            regime_duration=regime_duration,
            confidence=confidence
        )

    def _calculate_true_range(self, high: float, low: float, close: float) -> float:
        """Calculates True Range."""
        if len(self.closes) < 2:
            return high - low
        
        prev_close = self.closes[-2]
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        return max(tr1, tr2, tr3)

    def _calculate_directional_movement(self, high: float, low: float) -> Tuple[float, float]:
        """Calculates +DM and -DM."""
        if len(self.highs) < 2:
            return 0.0, 0.0
        
        prev_high = self.highs[-2]
        prev_low = self.lows[-2]
        
        up_move = high - prev_high
        down_move = prev_low - low
        
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
        
        return plus_dm, minus_dm

    def _calculate_adx(self) -> Tuple[float, float, float]:
        """
        Calculates ADX, +DI, and -DI using Wilder's smoothing.
        """
        period = self.adx_period
        
        if len(self.tr_values) < period:
            return 0.0, 0.0, 0.0
        
        # Get recent values
        tr_list = list(self.tr_values)[-period:]
        plus_dm_list = list(self.plus_dm)[-period:]
        minus_dm_list = list(self.minus_dm)[-period:]
        
        # Smoothed values (Wilder's EMA)
        atr = self._wilders_smooth(tr_list)
        smoothed_plus_dm = self._wilders_smooth(plus_dm_list)
        smoothed_minus_dm = self._wilders_smooth(minus_dm_list)
        
        # Directional Indicators
        if atr == 0:
            return 0.0, 0.0, 0.0
        
        plus_di = 100 * smoothed_plus_dm / atr
        minus_di = 100 * smoothed_minus_dm / atr
        
        # DX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx = 0.0
        else: 
            dx = 100 * abs(plus_di - minus_di) / di_sum
        
        # ADX (smoothed DX) - simplified using recent DX values
        # For proper ADX, we'd need to track DX history
        # Using current DX as approximation for simplicity
        adx = dx
        
        return adx, plus_di, minus_di

    def _wilders_smooth(self, values: List[float]) -> float:
        """Wilder's smoothing method."""
        if not values:
            return 0.0
        
        period = len(values)
        
        # Initial SMA
        result = sum(values[: period]) / period
        
        # Apply smoothing
        for val in values[period:]:
            result = (result * (period - 1) + val) / period
        
        return result

    def _calculate_atr(self) -> float:
        """Calculates Average True Range."""
        if len(self.tr_values) < self.atr_period:
            return 0.0
        
        tr_list = list(self.tr_values)[-self.atr_period:]
        return sum(tr_list) / len(tr_list)

    def _calculate_atr_percentile(self, current_atr: float) -> float:
        """
        Calculates where current ATR sits in historical range.
        Returns 0-100 percentile.
        """
        if len(self.atr_history) < 20:
            return 50.0
        
        atr_list = sorted(list(self.atr_history))
        
        # Find percentile
        count_below = sum(1 for x in atr_list if x < current_atr)
        percentile = (count_below / len(atr_list)) * 100
        
        return percentile

    def _get_trend_direction(self, plus_di: float, minus_di: float) -> str:
        """Determines trend direction from DI values."""
        diff = plus_di - minus_di
        
        if diff > 5:
            return 'UP'
        elif diff < -5:
            return 'DOWN'
        else:
            return 'NONE'

    def _update_swing_points(self):
        """
        Identifies swing highs and lows for structure analysis.
        A swing high:  Higher than 2 candles before and after.
        """
        if len(self.highs) < 5:
            return
        
        # Check for swing high (3 candles ago)
        idx = -3
        if (self.highs[idx] > self.highs[idx-1] and 
            self.highs[idx] > self.highs[idx-2] and
            self.highs[idx] > self.highs[idx+1] and 
            self.highs[idx] >= self.highs[idx+2]):
            self.swing_highs.append((self.candle_count + idx, self.highs[idx]))
        
        # Check for swing low
        if (self.lows[idx] < self.lows[idx-1] and 
            self.lows[idx] < self.lows[idx-2] and
            self.lows[idx] < self.lows[idx+1] and 
            self.lows[idx] <= self.lows[idx+2]):
            self.swing_lows.append((self.candle_count + idx, self.lows[idx]))

    def _detect_regime(self, adx: float, atr: float, atr_percentile: float,
                       plus_di: float, minus_di:  float) -> MarketRegime:
        """
        Main regime detection logic.
        
        Priority: 
        1.VOLATILE (overrides everything if ATR extreme)
        2.TRENDING_UP / TRENDING_DOWN (if ADX strong)
        3.RANGING (default)
        """
        
        # 1.Check for VOLATILE first
        if atr_percentile > 90:  # Top 10% ATR
            return MarketRegime.VOLATILE
        
        avg_atr = np.mean(list(self.atr_history)) if self.atr_history else atr
        if avg_atr > 0 and atr > avg_atr * self.atr_volatile_mult:
            return MarketRegime.VOLATILE
        
        # 2.Check for TRENDING
        if adx >= self.adx_trending:
            # Strong trend detected
            if plus_di > minus_di:
                # Confirm with structure
                if self._is_making_higher_highs():
                    return MarketRegime.TRENDING_UP
                return MarketRegime.TRENDING_UP  # Trust ADX even without structure
            else: 
                if self._is_making_lower_lows():
                    return MarketRegime.TRENDING_DOWN
                return MarketRegime.TRENDING_DOWN
        
        # 3.Check for weak trend (borderline)
        if self.adx_ranging < adx < self.adx_trending:
            # Weak trend - could go either way
            # Use recent price action to decide
            if self._is_making_higher_highs() and plus_di > minus_di:
                return MarketRegime.TRENDING_UP
            elif self._is_making_lower_lows() and minus_di > plus_di:
                return MarketRegime.TRENDING_DOWN
        
        # 4.Default to RANGING
        return MarketRegime.RANGING

    def _is_making_higher_highs(self) -> bool:
        """Checks if price is making higher highs and higher lows."""
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            return False
        
        # Get last 2 swing points
        recent_highs = [sh[1] for sh in list(self.swing_highs)[-2:]]
        recent_lows = [sl[1] for sl in list(self.swing_lows)[-2:]]
        
        higher_high = recent_highs[-1] > recent_highs[-2]
        higher_low = recent_lows[-1] > recent_lows[-2]
        
        return higher_high and higher_low

    def _is_making_lower_lows(self) -> bool:
        """Checks if price is making lower highs and lower lows."""
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            return False
        
        recent_highs = [sh[1] for sh in list(self.swing_highs)[-2:]]
        recent_lows = [sl[1] for sl in list(self.swing_lows)[-2:]]
        
        lower_high = recent_highs[-1] < recent_highs[-2]
        lower_low = recent_lows[-1] < recent_lows[-2]
        
        return lower_high and lower_low

    def _calculate_confidence(self, adx: float, atr_percentile:  float, 
                             duration: int) -> float:
        """
        Calculates confidence in current regime detection.
        
        Factors:
        - ADX strength (higher = more confident in trend)
        - Regime duration (longer = more confident)
        - ATR stability (less volatile = more confident)
        """
        confidence = 50.0  # Base
        
        # ADX contribution
        if adx > 40:
            confidence += 25
        elif adx > 30:
            confidence += 15
        elif adx > 25:
            confidence += 10
        elif adx < 15:
            confidence -= 10
        
        # Duration contribution
        if duration > 20:
            confidence += 15
        elif duration > 10:
            confidence += 10
        elif duration > 5:
            confidence += 5
        
        # Volatility stability
        if 30 <= atr_percentile <= 70:
            confidence += 10  # Normal volatility = stable
        elif atr_percentile > 85 or atr_percentile < 15:
            confidence -= 10  # Extreme = less stable
        
        return max(0, min(100, confidence))

    def get_regime_simple(self) -> str:
        """Returns simplified regime string for strategy mapping."""
        if self.current_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            return "TRENDING"
        elif self.current_regime == MarketRegime.VOLATILE:
            return "VOLATILE"
        else:
            return "RANGING"

    def is_ready(self) -> bool:
        """Checks if detector has enough data."""
        return self.is_warmed_up


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Regime Detector...\n")
    
    # Mock config
    class MockConfig:
        class Regime:
            ADX_TRENDING_THRESHOLD = 25
            ADX_STRONG_TREND_THRESHOLD = 40
            ADX_RANGING_THRESHOLD = 20
            ATR_PERIOD = 14
            ATR_VOLATILE_MULTIPLIER = 1.5
            ATR_LOW_VOL_MULTIPLIER = 0.7
            REGIME_CONFIRMATION_CANDLES = 3
    
    detector = RegimeDetector(MockConfig())
    
    # Simulate trending up market
    base_price = 24000
    print("Simulating UPTREND...")
    for i in range(30):
        high = base_price + i * 5 + 10
        low = base_price + i * 5 - 5
        close = base_price + i * 5 + 3
        
        state = detector.update(high, low, close)
    
    print(f"Regime: {state.regime.value}")
    print(f"ADX: {state.adx:.1f}")
    print(f"+DI: {state.plus_di:.1f} | -DI: {state.minus_di:.1f}")
    print(f"ATR: {state.atr:.1f}")
    print(f"Confidence: {state.confidence:.0f}%")
    
    print("\n✅ Regime Detector Test Complete!")