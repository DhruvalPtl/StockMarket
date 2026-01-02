"""
LIQUIDITY MAPPER
Identifies key price levels where liquidity clusters exist. 

Key Levels:
- Max Pain Strike (where most options expire worthless)
- High OI Strikes (resistance/support from option writers)
- Swing Highs/Lows (stop-loss clusters)
- Round Numbers (psychological levels)
- VWAP (institutional benchmark)

These levels act as: 
1. Magnets (price gravitates toward them)
2. Reversal zones (price bounces off them)
3. Breakout triggers (when broken, acceleration follows)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque
from datetime import datetime
import math

import sys
import os
sys.path.append(os. path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_intelligence.market_context import KeyLevel


@dataclass
class SwingPoint:
    """Represents a swing high or low."""
    price: float
    index: int
    point_type: str  # 'HIGH' or 'LOW'
    strength: int    # How many times tested
    timestamp: datetime


@dataclass
class LiquidityZone:
    """Represents a zone where stop-losses likely cluster."""
    price_low: float
    price_high: float
    zone_type: str   # 'ABOVE_RESISTANCE', 'BELOW_SUPPORT'
    estimated_stops: int  # Estimated number of stops
    hunted:  bool = False  # Has this zone been swept?


class LiquidityMapper:
    """
    Maps key liquidity levels in the market. 
    
    Provides: 
    1. Max Pain calculation (option expiry magnet)
    2. Key OI strikes (writer-created levels)
    3. Swing point detection (stop-loss clusters)
    4. Round number levels
    5. Dynamic support/resistance
    """
    
    def __init__(self, config):
        self.config = config
        
        # Settings
        self.swing_lookback = config. Liquidity. SWING_LOOKBACK
        self.round_number_interval = config.Liquidity.ROUND_NUMBER_INTERVAL
        self.max_pain_range = config.Liquidity.MAX_PAIN_STRIKE_RANGE
        self.level_touch_threshold = config.Liquidity.LEVEL_TOUCH_THRESHOLD
        
        # Price history for swing detection
        self.highs:  deque[float] = deque(maxlen=200)
        self.lows: deque[float] = deque(maxlen=200)
        self.closes: deque[float] = deque(maxlen=200)
        
        # Swing points
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        
        # Key levels
        self. key_levels: List[KeyLevel] = []
        self.liquidity_zones: List[LiquidityZone] = []
        
        # Max Pain
        self.max_pain_strike = 0
        self.max_pain_value = 0  # Total pain at max pain strike
        
        # High OI strikes
        self.resistance_strikes: List[int] = []  # High CE OI
        self.support_strikes: List[int] = []     # High PE OI
        
        # Tracking
        self.candle_count = 0
        self.current_price = 0
        self.atm_strike = 0
        
        # VWAP
        self.vwap = 0
        
        # Opening range
        self.opening_range_high = 0
        self.opening_range_low = 0
        self.opening_range_set = False

    def update(self,
               high: float,
               low: float,
               close: float,
               vwap: float,
               option_chain: Dict[int, Dict],
               atm_strike: int) -> List[KeyLevel]:
        """
        Main update method. 
        
        Args:
            high:  Candle high
            low: Candle low
            close:  Candle close
            vwap: Current VWAP
            option_chain:  Dict of {strike: {'ce_oi': x, 'pe_oi': y}}
            atm_strike: Current ATM strike
            
        Returns:
            List of KeyLevel objects
        """
        self.candle_count += 1
        self.current_price = close
        self.atm_strike = atm_strike
        self.vwap = vwap
        
        # Store prices
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        # Set opening range (first 15 minutes = ~15 candles on 1min)
        if not self.opening_range_set:
            self._update_opening_range(high, low)
        
        # Detect swing points
        self._detect_swing_points()
        
        # Calculate max pain
        if option_chain:
            self._calculate_max_pain(option_chain)
            self._find_high_oi_strikes(option_chain)
        
        # Build key levels list
        self._build_key_levels()
        
        # Identify liquidity zones
        self._identify_liquidity_zones()
        
        return self.key_levels

    def _update_opening_range(self, high:  float, low: float):
        """Updates opening range during first 15-30 minutes."""
        # First candle sets initial range
        if self.candle_count == 1:
            self.opening_range_high = high
            self.opening_range_low = low
        elif self.candle_count <= 15:  # First 15 candles
            self.opening_range_high = max(self.opening_range_high, high)
            self.opening_range_low = min(self.opening_range_low, low)
        else:
            self.opening_range_set = True

    def _detect_swing_points(self):
        """
        Detects swing highs and lows. 
        
        A swing high:  Higher than N candles before and after
        A swing low: Lower than N candles before and after
        """
        if len(self. highs) < self.swing_lookback * 2 + 1:
            return
        
        # Check the middle candle (swing_lookback candles ago)
        idx = -self.swing_lookback - 1
        
        # Get the candidate
        candidate_high = self. highs[idx]
        candidate_low = self.lows[idx]
        
        # Check for swing high
        is_swing_high = True
        for i in range(-self.swing_lookback * 2, 0):
            if i == idx:
                continue
            if self.highs[i] >= candidate_high: 
                is_swing_high = False
                break
        
        if is_swing_high:
            # Check if we already have this level (within tolerance)
            existing = self._find_existing_swing(candidate_high, 'HIGH')
            if existing:
                existing.strength += 1
            else:
                self.swing_highs.append(SwingPoint(
                    price=candidate_high,
                    index=self.candle_count + idx,
                    point_type='HIGH',
                    strength=1,
                    timestamp=datetime.now()
                ))
        
        # Check for swing low
        is_swing_low = True
        for i in range(-self.swing_lookback * 2, 0):
            if i == idx: 
                continue
            if self.lows[i] <= candidate_low:
                is_swing_low = False
                break
        
        if is_swing_low: 
            existing = self._find_existing_swing(candidate_low, 'LOW')
            if existing:
                existing.strength += 1
            else: 
                self.swing_lows.append(SwingPoint(
                    price=candidate_low,
                    index=self. candle_count + idx,
                    point_type='LOW',
                    strength=1,
                    timestamp=datetime. now()
                ))
        
        # Cleanup old swing points (keep last 20)
        self.swing_highs = self.swing_highs[-20:]
        self.swing_lows = self. swing_lows[-20:]

    def _find_existing_swing(self, price: float, point_type: str) -> Optional[SwingPoint]:
        """Finds existing swing point within tolerance."""
        tolerance = 10  # points
        
        points = self.swing_highs if point_type == 'HIGH' else self.swing_lows
        
        for point in points:
            if abs(point.price - price) <= tolerance:
                return point
        
        return None

    def _calculate_max_pain(self, option_chain: Dict[int, Dict]):
        """
        Calculates Max Pain strike.
        
        Max Pain = Strike where total loss for option buyers is maximum
                 = Strike where total profit for option writers is maximum
        
        This is where price tends to gravitate toward on expiry.
        """
        if not option_chain: 
            return
        
        strikes = sorted(option_chain. keys())
        
        if not strikes:
            return
        
        min_pain = float('inf')
        max_pain_strike = strikes[len(strikes) // 2]  # Default to middle
        
        for test_strike in strikes: 
            total_pain = 0
            
            for strike, data in option_chain.items():
                ce_oi = data. get('ce_oi', 0)
                pe_oi = data.get('pe_oi', 0)
                
                # CE pain: If price < strike, CE expires worthless (0 pain)
                #          If price > strike, CE buyers profit = (price - strike) * OI
                if test_strike > strike:
                    ce_pain = (test_strike - strike) * ce_oi
                else: 
                    ce_pain = 0
                
                # PE pain: If price > strike, PE expires worthless (0 pain)
                #          If price < strike, PE buyers profit = (strike - price) * OI
                if test_strike < strike:
                    pe_pain = (strike - test_strike) * pe_oi
                else: 
                    pe_pain = 0
                
                total_pain += ce_pain + pe_pain
            
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike
        
        self.max_pain_strike = max_pain_strike
        self.max_pain_value = min_pain

    def _find_high_oi_strikes(self, option_chain: Dict[int, Dict]):
        """
        Identifies strikes with highest CE and PE OI. 
        
        High CE OI = Resistance (writers don't want price above)
        High PE OI = Support (writers don't want price below)
        """
        if not option_chain:
            return
        
        # Sort by CE OI and PE OI
        ce_sorted = sorted(option_chain.items(), 
                          key=lambda x: x[1].get('ce_oi', 0), 
                          reverse=True)
        pe_sorted = sorted(option_chain.items(), 
                          key=lambda x: x[1].get('pe_oi', 0), 
                          reverse=True)
        
        # Top 3 CE OI strikes (resistance)
        self.resistance_strikes = [s[0] for s in ce_sorted[:3] if s[0] > self.atm_strike]
        
        # Top 3 PE OI strikes (support)
        self.support_strikes = [s[0] for s in pe_sorted[: 3] if s[0] < self. atm_strike]

    def _build_key_levels(self):
        """Builds the master list of key levels."""
        self.key_levels = []
        
        # 1. Add VWAP
        if self.vwap > 0:
            self.key_levels.append(KeyLevel(
                price=self.vwap,
                level_type='PIVOT',
                strength=5,  # High importance
                source='VWAP'
            ))
        
        # 2. Add Max Pain
        if self.max_pain_strike > 0:
            self.key_levels.append(KeyLevel(
                price=float(self.max_pain_strike),
                level_type='MAX_PAIN',
                strength=4,
                source='OI'
            ))
        
        # 3. Add OI-based resistance levels
        for strike in self.resistance_strikes[: 2]: 
            self.key_levels.append(KeyLevel(
                price=float(strike),
                level_type='RESISTANCE',
                strength=4,
                source='OI'
            ))
        
        # 4. Add OI-based support levels
        for strike in self.support_strikes[:2]: 
            self.key_levels.append(KeyLevel(
                price=float(strike),
                level_type='SUPPORT',
                strength=4,
                source='OI'
            ))
        
        # 5. Add swing highs as resistance
        for swing in self.swing_highs[-5:]:
            if swing.price > self.current_price:
                self.key_levels.append(KeyLevel(
                    price=swing.price,
                    level_type='RESISTANCE',
                    strength=min(5, swing. strength),
                    source='SWING'
                ))
        
        # 6. Add swing lows as support
        for swing in self.swing_lows[-5:]:
            if swing.price < self.current_price:
                self.key_levels.append(KeyLevel(
                    price=swing. price,
                    level_type='SUPPORT',
                    strength=min(5, swing.strength),
                    source='SWING'
                ))
        
        # 7. Add round numbers
        round_levels = self._get_round_number_levels()
        for level in round_levels:
            level_type = 'RESISTANCE' if level > self.current_price else 'SUPPORT'
            self.key_levels.append(KeyLevel(
                price=level,
                level_type=level_type,
                strength=2,
                source='ROUND_NUMBER'
            ))
        
        # 8. Add opening range levels
        if self.opening_range_set:
            self.key_levels. append(KeyLevel(
                price=self. opening_range_high,
                level_type='RESISTANCE',
                strength=3,
                source='OPENING_RANGE'
            ))
            self.key_levels.append(KeyLevel(
                price=self.opening_range_low,
                level_type='SUPPORT',
                strength=3,
                source='OPENING_RANGE'
            ))
        
        # Sort by distance from current price
        self.key_levels.sort(key=lambda x: abs(x.price - self.current_price))

    def _get_round_number_levels(self) -> List[float]:
        """Gets round number levels near current price."""
        if self.current_price == 0:
            return []
        
        levels = []
        interval = self.round_number_interval
        
        # Find nearest round number below
        base = math.floor(self. current_price / interval) * interval
        
        # Get 2 above and 2 below
        for i in range(-2, 3):
            level = base + i * interval
            if level != self.current_price:  # Exclude exact current price
                levels. append(level)
        
        return levels

    def _identify_liquidity_zones(self):
        """
        Identifies zones where stop-losses likely cluster.
        
        Stop-losses typically sit: 
        - Just below swing lows (for longs)
        - Just above swing highs (for shorts)
        """
        self.liquidity_zones = []
        
        # Zones above swing highs (short stop-losses)
        for swing in self.swing_highs[-3:]:
            if swing.price > self.current_price:
                zone = LiquidityZone(
                    price_low=swing.price,
                    price_high=swing.price + 15,  # 15 points buffer
                    zone_type='ABOVE_RESISTANCE',
                    estimated_stops=swing.strength * 1000,  # Rough estimate
                    hunted=False
                )
                self.liquidity_zones.append(zone)
        
        # Zones below swing lows (long stop-losses)
        for swing in self. swing_lows[-3:]:
            if swing.price < self.current_price:
                zone = LiquidityZone(
                    price_low=swing.price - 15,
                    price_high=swing.price,
                    zone_type='BELOW_SUPPORT',
                    estimated_stops=swing.strength * 1000,
                    hunted=False
                )
                self.liquidity_zones.append(zone)

    def get_nearest_support(self) -> float:
        """Returns nearest support level below current price."""
        supports = [l for l in self. key_levels 
                   if l.level_type == 'SUPPORT' and l.price < self.current_price]
        
        if supports:
            return max(s.price for s in supports)  # Highest support below price
        return 0

    def get_nearest_resistance(self) -> float:
        """Returns nearest resistance level above current price."""
        resistances = [l for l in self.key_levels 
                      if l.level_type == 'RESISTANCE' and l.price > self.current_price]
        
        if resistances: 
            return min(r.price for r in resistances)  # Lowest resistance above price
        return 0

    def get_max_pain(self) -> int:
        """Returns max pain strike."""
        return self.max_pain_strike

    def get_opening_range(self) -> Tuple[float, float, bool]:
        """Returns opening range (high, low, is_set)."""
        return self.opening_range_high, self.opening_range_low, self.opening_range_set

    def is_near_key_level(self, price: float, tolerance: float = 10) -> Tuple[bool, Optional[KeyLevel]]: 
        """
        Checks if price is near a key level. 
        
        Returns:
            (is_near, nearest_level)
        """
        for level in self.key_levels:
            if abs(level.price - price) <= tolerance:
                return True, level
        return False, None

    def get_liquidity_zone_nearby(self, price:  float) -> Optional[LiquidityZone]:
        """Returns liquidity zone if price is approaching one."""
        for zone in self.liquidity_zones:
            # Check if within 20 points of zone
            if zone.price_low - 20 <= price <= zone.price_high + 20:
                return zone
        return None

    def check_liquidity_sweep(self, high: float, low:  float) -> Optional[LiquidityZone]:
        """
        Checks if current candle swept a liquidity zone. 
        
        A sweep:  Price briefly enters zone then reverses. 
        This is a potential trade setup! 
        """
        for zone in self. liquidity_zones: 
            if zone.hunted:
                continue
            
            # Check if candle wick entered zone
            if zone.zone_type == 'ABOVE_RESISTANCE': 
                if high >= zone.price_low and low < zone.price_low:
                    # Wick went above, but closed below = sweep
                    zone.hunted = True
                    return zone
            
            elif zone.zone_type == 'BELOW_SUPPORT': 
                if low <= zone.price_high and high > zone.price_high:
                    # Wick went below, but closed above = sweep
                    zone. hunted = True
                    return zone
        
        return None

    def print_levels_summary(self):
        """Prints a summary of key levels."""
        print(f"\n{'='*50}")
        print(f"📊 KEY LEVELS @ {self.current_price:.2f}")
        print(f"{'='*50}")
        
        print(f"\n🎯 Max Pain: {self. max_pain_strike}")
        print(f"📈 VWAP: {self.vwap:.2f}")
        
        if self.opening_range_set:
            print(f"🌅 Opening Range: {self.opening_range_low:.2f} - {self.opening_range_high:.2f}")
        
        print(f"\n🔴 Resistance:")
        for level in self.key_levels:
            if level.level_type == 'RESISTANCE' and level.price > self.current_price:
                print(f"   {level.price:. 2f} ({level.source}, strength:{level.strength})")
        
        print(f"\n🟢 Support:")
        for level in self.key_levels:
            if level.level_type == 'SUPPORT' and level.price < self.current_price:
                print(f"   {level.price:.2f} ({level.source}, strength:{level. strength})")
        
        print(f"\n💧 Liquidity Zones:")
        for zone in self.liquidity_zones: 
            status = "✓ Hunted" if zone.hunted else "Active"
            print(f"   {zone.price_low:. 2f}-{zone.price_high:.2f} ({zone.zone_type}) [{status}]")
        
        print(f"{'='*50}\n")


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n🔬 Testing Liquidity Mapper.. .\n")
    
    # Mock config
    class MockConfig:
        class Liquidity:
            SWING_LOOKBACK = 5
            ROUND_NUMBER_INTERVAL = 100
            MAX_PAIN_STRIKE_RANGE = 500
            LEVEL_TOUCH_THRESHOLD = 3
    
    mapper = LiquidityMapper(MockConfig())
    
    # Simulate price data with swing points
    print("Simulating market with swing points...")
    
    # First, create opening range
    for i in range(15):
        high = 24050 + (i % 3) * 10
        low = 23950 - (i % 3) * 10
        close = 24000 + (i % 5) * 5
        
        mapper.update(high, low, close, 24000, {}, 24000)
    
    print(f"Opening Range: {mapper.opening_range_low} - {mapper.opening_range_high}")
    print(f"Opening Range Set: {mapper.opening_range_set}")
    
    # Create some swing points
    prices = [
        (24100, 24050, 24080),  # Up move
        (24120, 24070, 24110),
        (24150, 24100, 24140),  # Swing high forming
        (24140, 24080, 24090),  # Pullback
        (24100, 24050, 24060),
        (24080, 24000, 24010),  # Swing low
        (24050, 24010, 24040),
        (24080, 24030, 24070),  # Up move
        (24100, 24050, 24090),
    ]
    
    # Mock option chain
    option_chain = {
        23800: {'ce_oi': 500000, 'pe_oi': 1200000},
        23900: {'ce_oi': 600000, 'pe_oi': 1000000},
        24000: {'ce_oi': 800000, 'pe_oi': 900000},
        24100: {'ce_oi': 1100000, 'pe_oi': 600000},
        24200: {'ce_oi': 1300000, 'pe_oi': 400000},
    }
    
    for high, low, close in prices:
        mapper.update(high, low, close, 24020, option_chain, 24000)
    
    # Print summary
    mapper.print_levels_summary()
    
    # Test specific functions
    print(f"Nearest Support: {mapper.get_nearest_support():.2f}")
    print(f"Nearest Resistance:  {mapper.get_nearest_resistance():.2f}")
    print(f"Max Pain: {mapper.get_max_pain()}")
    
    near, level = mapper.is_near_key_level(24010)
    if near:
        print(f"Price near key level: {level}")
    
    print("\n✅ Liquidity Mapper Test Complete!")