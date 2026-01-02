"""
ORDER FLOW TRACKER
Tracks institutional activity through OI changes and volume analysis. 

What it detects:
- Long Buildup:  Price ↑ + OI ↑ (Strong bullish)
- Short Buildup: Price ↓ + OI ↑ (Strong bearish)
- Long Unwinding: Price ↓ + OI ↓ (Weak bearish - longs exiting)
- Short Covering: Price ↑ + OI ↓ (Weak bullish - shorts exiting)

Also tracks:
- Volume spikes (institutional activity)
- CE vs PE OI imbalance
- Smart money direction inference
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque
from enum import Enum
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path. dirname(os.path.abspath(__file__))))

from market_intelligence.market_context import OrderFlowState


class OISignal(Enum):
    """Open Interest based signals."""
    LONG_BUILDUP = "LONG_BUILDUP"           # Price ↑ + OI ↑
    SHORT_BUILDUP = "SHORT_BUILDUP"         # Price ↓ + OI ↑
    LONG_UNWINDING = "LONG_UNWINDING"       # Price ↓ + OI ↓
    SHORT_COVERING = "SHORT_COVERING"       # Price ↑ + OI ↓
    NEUTRAL = "NEUTRAL"


class VolumeState(Enum):
    """Volume classification."""
    SPIKE = "SPIKE"           # > 2x average
    HIGH = "HIGH"             # > 1.5x average
    NORMAL = "NORMAL"         # 0. 7x - 1.5x average
    DRY = "DRY"               # < 0.5x average
    

@dataclass
class OISnapshot:
    """Snapshot of OI data at a point in time."""
    timestamp: datetime
    total_ce_oi: int
    total_pe_oi: int
    pcr:  float
    atm_ce_oi: int
    atm_pe_oi:  int
    price:  float


@dataclass 
class StrikeOIData:
    """OI data for a specific strike."""
    strike: int
    ce_oi: int
    pe_oi: int
    ce_oi_change: int
    pe_oi_change: int
    ce_iv: float
    pe_iv: float


class OrderFlowTracker:
    """
    Tracks order flow through OI and volume analysis.
    
    Key insights:
    1. OI + Price relationship tells us WHO is in control
    2. Volume spikes indicate institutional activity
    3. CE vs PE OI changes reveal market maker positioning
    """
    
    def __init__(self, config):
        self.config = config
        
        # Thresholds from config
        self. oi_significant_change = config.OrderFlow.OI_SIGNIFICANT_CHANGE_PCT
        self. oi_buildup_threshold = config.OrderFlow.OI_BUILDUP_THRESHOLD
        self.volume_spike_mult = config.OrderFlow.VOLUME_SPIKE_MULTIPLIER
        self. volume_dry_mult = config. OrderFlow.VOLUME_DRY_MULTIPLIER
        self. oi_lookback = config.OrderFlow. OI_LOOKBACK_PERIODS
        
        # OI History
        self. oi_history: deque[OISnapshot] = deque(maxlen=100)
        self.strike_oi_history: Dict[int, deque] = {}  # strike -> deque of OI values
        
        # Price history (for OI-Price correlation)
        self.price_history: deque[float] = deque(maxlen=100)
        
        # Volume history
        self.volume_history: deque[float] = deque(maxlen=50)
        
        # Current state
        self.current_signal = OISignal. NEUTRAL
        self. current_volume_state = VolumeState.NORMAL
        self.smart_money_direction = "NEUTRAL"
        
        # Strike-level tracking
        self.max_ce_oi_strike = 0
        self.max_pe_oi_strike = 0
        self.max_ce_oi_change_strike = 0
        self.max_pe_oi_change_strike = 0
        
        # IV tracking
        self. iv_history: deque[float] = deque(maxlen=50)
        self.current_iv_percentile = 50.0
        
        # Warmup
        self.update_count = 0
        self.is_warmed_up = False

    def update(self, 
               price: float,
               total_ce_oi: int,
               total_pe_oi: int,
               volume: float,
               strike_data: Dict[int, StrikeOIData],
               atm_strike:  int) -> OrderFlowState: 
        """
        Main update method.  Call with each data refresh.
        
        Args:
            price: Current spot/future price
            total_ce_oi:  Total Call OI
            total_pe_oi:  Total Put OI
            volume: Current candle volume
            strike_data: Dict of strike -> StrikeOIData
            atm_strike: Current ATM strike
            
        Returns: 
            OrderFlowState with current analysis
        """
        self.update_count += 1
        self.price_history. append(price)
        self.volume_history.append(volume)
        
        # Calculate PCR
        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
        
        # Get ATM OI
        atm_ce_oi = 0
        atm_pe_oi = 0
        if atm_strike in strike_data: 
            atm_ce_oi = strike_data[atm_strike].ce_oi
            atm_pe_oi = strike_data[atm_strike].pe_oi
        
        # Create and store snapshot
        snapshot = OISnapshot(
            timestamp=datetime.now(),
            total_ce_oi=total_ce_oi,
            total_pe_oi=total_pe_oi,
            pcr=pcr,
            atm_ce_oi=atm_ce_oi,
            atm_pe_oi=atm_pe_oi,
            price=price
        )
        self.oi_history.append(snapshot)
        
        # Update strike-level history
        self._update_strike_history(strike_data)
        
        # Calculate OI changes
        ce_oi_change, pe_oi_change = self._calculate_oi_changes()
        ce_oi_change_pct = (ce_oi_change / total_ce_oi * 100) if total_ce_oi > 0 else 0
        pe_oi_change_pct = (pe_oi_change / total_pe_oi * 100) if total_pe_oi > 0 else 0
        
        # Detect OI signal
        oi_signal = self._detect_oi_signal(price, total_ce_oi + total_pe_oi)
        self.current_signal = oi_signal
        
        # Analyze volume
        volume_state, relative_volume = self._analyze_volume(volume)
        self.current_volume_state = volume_state
        
        # Find max OI strikes
        self._find_max_oi_strikes(strike_data)
        
        # Infer smart money direction
        smart_money = self._infer_smart_money(
            ce_oi_change_pct, pe_oi_change_pct, oi_signal, pcr
        )
        self.smart_money_direction = smart_money
        
        # Update IV tracking
        self._update_iv_tracking(strike_data, atm_strike)
        
        # Warmup check
        if self.update_count >= 5:
            self.is_warmed_up = True
        
        return OrderFlowState(
            total_ce_oi=total_ce_oi,
            total_pe_oi=total_pe_oi,
            pcr=pcr,
            ce_oi_change=ce_oi_change,
            pe_oi_change=pe_oi_change,
            ce_oi_change_pct=ce_oi_change_pct,
            pe_oi_change_pct=pe_oi_change_pct,
            oi_signal=oi_signal. value,
            smart_money_direction=smart_money,
            volume_state=volume_state.value,
            relative_volume=relative_volume
        )

    def _update_strike_history(self, strike_data: Dict[int, StrikeOIData]):
        """Updates OI history for each strike."""
        for strike, data in strike_data.items():
            if strike not in self.strike_oi_history: 
                self.strike_oi_history[strike] = deque(maxlen=50)
            
            self.strike_oi_history[strike]. append({
                'ce_oi': data.ce_oi,
                'pe_oi': data.pe_oi,
                'timestamp': datetime.now()
            })

    def _calculate_oi_changes(self) -> Tuple[int, int]: 
        """Calculates OI change from lookback periods ago."""
        if len(self.oi_history) < self.oi_lookback + 1:
            return 0, 0
        
        current = self.oi_history[-1]
        previous = self.oi_history[-(self.oi_lookback + 1)]
        
        ce_change = current.total_ce_oi - previous.total_ce_oi
        pe_change = current.total_pe_oi - previous.total_pe_oi
        
        return ce_change, pe_change

    def _detect_oi_signal(self, current_price: float, current_total_oi: int) -> OISignal: 
        """
        Detects OI signal based on Price + OI relationship. 
        
        Logic:
        - Price ↑ + OI ↑ = LONG_BUILDUP (New longs entering)
        - Price ↓ + OI ↑ = SHORT_BUILDUP (New shorts entering)
        - Price ↓ + OI ↓ = LONG_UNWINDING (Longs exiting)
        - Price ↑ + OI ↓ = SHORT_COVERING (Shorts exiting)
        """
        if len(self. oi_history) < self.oi_lookback + 1:
            return OISignal.NEUTRAL
        
        if len(self.price_history) < self.oi_lookback + 1:
            return OISignal.NEUTRAL
        
        # Get previous values
        prev_snapshot = self.oi_history[-(self.oi_lookback + 1)]
        prev_price = self.price_history[-(self.oi_lookback + 1)]
        prev_total_oi = prev_snapshot. total_ce_oi + prev_snapshot.total_pe_oi
        
        # Calculate changes
        price_change = current_price - prev_price
        oi_change = current_total_oi - prev_total_oi
        
        # Calculate percentage changes
        price_change_pct = (price_change / prev_price * 100) if prev_price > 0 else 0
        oi_change_pct = (oi_change / prev_total_oi * 100) if prev_total_oi > 0 else 0
        
        # Thresholds for significance
        price_threshold = 0.05  # 0.05% price move
        oi_threshold = 1.0      # 1% OI change
        
        # Determine signal
        price_up = price_change_pct > price_threshold
        price_down = price_change_pct < -price_threshold
        oi_up = oi_change_pct > oi_threshold
        oi_down = oi_change_pct < -oi_threshold
        
        if price_up and oi_up: 
            return OISignal.LONG_BUILDUP
        elif price_down and oi_up:
            return OISignal.SHORT_BUILDUP
        elif price_down and oi_down:
            return OISignal. LONG_UNWINDING
        elif price_up and oi_down:
            return OISignal. SHORT_COVERING
        else:
            return OISignal.NEUTRAL

    def _analyze_volume(self, current_volume: float) -> Tuple[VolumeState, float]:
        """
        Analyzes volume relative to average.
        
        Returns:
            (VolumeState, relative_volume_ratio)
        """
        if len(self.volume_history) < 10:
            return VolumeState. NORMAL, 1.0
        
        # Calculate average (excluding current)
        avg_volume = sum(list(self.volume_history)[:-1]) / (len(self.volume_history) - 1)
        
        if avg_volume == 0:
            return VolumeState. NORMAL, 1.0
        
        relative = current_volume / avg_volume
        
        if relative >= self.volume_spike_mult:
            return VolumeState.SPIKE, relative
        elif relative >= 1.5: 
            return VolumeState.HIGH, relative
        elif relative <= self.volume_dry_mult:
            return VolumeState. DRY, relative
        else: 
            return VolumeState.NORMAL, relative

    def _find_max_oi_strikes(self, strike_data:  Dict[int, StrikeOIData]):
        """Finds strikes with maximum OI and maximum OI change."""
        if not strike_data:
            return
        
        max_ce_oi = 0
        max_pe_oi = 0
        max_ce_change = 0
        max_pe_change = 0
        
        for strike, data in strike_data.items():
            # Max OI
            if data.ce_oi > max_ce_oi: 
                max_ce_oi = data. ce_oi
                self.max_ce_oi_strike = strike
            if data.pe_oi > max_pe_oi: 
                max_pe_oi = data. pe_oi
                self.max_pe_oi_strike = strike
            
            # Max OI change (absolute)
            if abs(data.ce_oi_change) > max_ce_change:
                max_ce_change = abs(data.ce_oi_change)
                self. max_ce_oi_change_strike = strike
            if abs(data.pe_oi_change) > max_pe_change:
                max_pe_change = abs(data. pe_oi_change)
                self.max_pe_oi_change_strike = strike

    def _infer_smart_money(self, ce_change_pct: float, pe_change_pct: float,
                          oi_signal:  OISignal, pcr: float) -> str:
        """
        Infers smart money direction from order flow.
        
        Key insight: Option WRITERS (market makers) are usually right. 
        - If CE OI increasing fast → Resistance being created → BEARISH
        - If PE OI increasing fast → Support being created → BULLISH
        
        We trade WITH the writers (contrarian to buyers).
        """
        score = 0
        
        # OI Change analysis (contrarian)
        if ce_change_pct > self.oi_significant_change:
            score -= 1  # CE writers creating resistance = bearish
        if pe_change_pct > self. oi_significant_change:
            score += 1  # PE writers creating support = bullish
        
        # PCR analysis
        if pcr > 1.2: 
            score += 1  # High PCR = bullish
        elif pcr < 0.8:
            score -= 1  # Low PCR = bearish
        
        # OI Signal analysis
        if oi_signal == OISignal.LONG_BUILDUP: 
            score += 2
        elif oi_signal == OISignal.SHORT_BUILDUP: 
            score -= 2
        elif oi_signal == OISignal.SHORT_COVERING:
            score += 1  # Weak bullish
        elif oi_signal == OISignal.LONG_UNWINDING: 
            score -= 1  # Weak bearish
        
        # Determine direction
        if score >= 2:
            return "BULLISH"
        elif score <= -2:
            return "BEARISH"
        else: 
            return "NEUTRAL"

    def _update_iv_tracking(self, strike_data: Dict[int, StrikeOIData], atm_strike: int):
        """Updates IV tracking for volatility analysis."""
        if atm_strike not in strike_data:
            return
        
        atm_data = strike_data[atm_strike]
        
        # Average of CE and PE IV
        avg_iv = (atm_data.ce_iv + atm_data.pe_iv) / 2 if atm_data.ce_iv > 0 else 0
        
        if avg_iv > 0:
            self.iv_history. append(avg_iv)
            
            # Calculate percentile
            if len(self.iv_history) >= 20:
                sorted_iv = sorted(list(self.iv_history))
                count_below = sum(1 for x in sorted_iv if x < avg_iv)
                self.current_iv_percentile = (count_below / len(sorted_iv)) * 100

    def get_max_oi_strikes(self) -> Dict[str, int]:
        """Returns strikes with maximum OI."""
        return {
            'max_ce_oi':  self.max_ce_oi_strike,
            'max_pe_oi': self.max_pe_oi_strike,
            'max_ce_change':  self.max_ce_oi_change_strike,
            'max_pe_change': self.max_pe_oi_change_strike
        }

    def get_iv_percentile(self) -> float:
        """Returns current IV percentile."""
        return self.current_iv_percentile

    def is_volume_confirming(self, direction: str) -> bool:
        """
        Checks if volume confirms the trading direction.
        
        High volume on moves = confirmation
        Low volume on moves = suspect
        """
        if self.current_volume_state in [VolumeState.SPIKE, VolumeState.HIGH]:
            return True
        return False

    def get_oi_buildup_type(self) -> str:
        """Returns current OI buildup type as string."""
        return self.current_signal.value

    def is_ready(self) -> bool:
        """Checks if tracker has enough data."""
        return self. is_warmed_up


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Order Flow Tracker.. .\n")
    
    # Mock config
    class MockConfig:
        class OrderFlow:
            OI_SIGNIFICANT_CHANGE_PCT = 5
            OI_BUILDUP_THRESHOLD = 10
            VOLUME_SPIKE_MULTIPLIER = 2.0
            VOLUME_DRY_MULTIPLIER = 0.5
            OI_LOOKBACK_PERIODS = 5
    
    tracker = OrderFlowTracker(MockConfig())
    
    # Simulate LONG_BUILDUP:  Price up + OI up
    print("Simulating LONG_BUILDUP (Price ↑ + OI ↑)...")
    
    base_price = 24000
    base_ce_oi = 1000000
    base_pe_oi = 1200000
    
    for i in range(10):
        price = base_price + i * 10  # Price going up
        ce_oi = base_ce_oi + i * 50000  # CE OI increasing
        pe_oi = base_pe_oi + i * 60000  # PE OI increasing
        volume = 100000 + i * 20000  # Volume increasing
        
        strike_data = {
            24000: StrikeOIData(
                strike=24000,
                ce_oi=500000 + i * 10000,
                pe_oi=600000 + i * 12000,
                ce_oi_change=10000,
                pe_oi_change=12000,
                ce_iv=15.0,
                pe_iv=16.0
            )
        }
        
        state = tracker.update(price, ce_oi, pe_oi, volume, strike_data, 24000)
    
    print(f"\nOI Signal: {state. oi_signal}")
    print(f"Smart Money:  {state.smart_money_direction}")
    print(f"PCR: {state. pcr:. 2f}")
    print(f"Volume State: {state.volume_state}")
    print(f"Relative Volume: {state.relative_volume:. 1f}x")
    print(f"CE OI Change: {state.ce_oi_change_pct: +.1f}%")
    print(f"PE OI Change: {state.pe_oi_change_pct:+.1f}%")
    
    print("\n" + "="*50)
    print("Simulating SHORT_BUILDUP (Price ↓ + OI ↑)...")
    
    tracker = OrderFlowTracker(MockConfig())
    
    for i in range(10):
        price = base_price - i * 10  # Price going DOWN
        ce_oi = base_ce_oi + i * 70000  # OI still increasing
        pe_oi = base_pe_oi + i * 50000
        volume = 150000
        
        strike_data = {
            24000: StrikeOIData(
                strike=24000, ce_oi=500000, pe_oi=600000,
                ce_oi_change=5000, pe_oi_change=5000,
                ce_iv=18.0, pe_iv=17.0
            )
        }
        
        state = tracker.update(price, ce_oi, pe_oi, volume, strike_data, 24000)
    
    print(f"\nOI Signal: {state.oi_signal}")
    print(f"Smart Money:  {state.smart_money_direction}")
    
    print("\n✅ Order Flow Tracker Test Complete!")