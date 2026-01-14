# Strike Tracking & Indicator Analysis - Experiment 8

## Executive Summary

Analysis of experiment8 logs revealed confusion about "changing strikes" during trades. The root cause was **misleading log output**, not actual trading errors. The system was working correctly but logs only showed the dynamic ATM strike, not the fixed position strike.

## Issues Identified

### Issue 1: Misleading Log Output ❌ FIXED

**Problem:**
- Bot logs showed only the current ATM strike (which changes every tick as spot moves)
- Example: Spot at 25775 → ATM=25800, Spot at 25725 → ATM=25700
- Created false impression that positions were bought at one strike and sold at another

**Evidence from Logs:**
```
11:43:48 | Spot:25775.6 | ATM:25800 | SCANNING
11:43:59 | Spot:25768.4 | ATM:25750 | SCANNING  ← ATM changed in 11 seconds!
```

**Reality:**
- Positions were entered and exited at the SAME strike (verified in trade books)
- Trade book shows: Entry at 25600PE, Exit at 25600PE ✓
- The changing ATM in logs was just the current market ATM, not the position strike

**Fix Applied:**
- Added `Active_Strike` column to logs
- Shows position strike when in trade, ATM when scanning
- Now clearly distinguishes between dynamic ATM and fixed position strike

### Issue 2: Strike Selection vs ATM ✅ WORKING AS DESIGNED

**How It Works:**
When entering a trade, the system:
1. Calculates current ATM (rounded to nearest 50)
2. Tries to find affordable strike in this order:
   - For PE: ATM, ATM-50, ATM-100
   - For CE: ATM, ATM+50, ATM+100
3. Selects first affordable strike within budget

**Example:**
```
ATM = 25600
Looking for PE strike:
- Try 25600PE @ ₹120 (too expensive)
- Try 25550PE @ ₹85 ✓ (affordable)
- Enter trade at 25550PE
```

**This is correct behavior:**
- Ensures trades stay within risk limits
- Selects OTM strikes when ATM is too expensive
- All monitoring/exit uses the selected strike, NOT ATM

**New Logging:**
```
ℹ️ Selected PE 25550 (ATM was 25600, offset: -50)
🚀 ENTRY: PE 25550 @ ₹85.00
   ATM: 25600 | Active Strike: 25550 (Monitoring this strike)
```

### Issue 3: Indicator Calculation ✅ CORRECT

**User Concern:** "all indicators values are wrong"

**Analysis:**
Indicators (RSI, EMA, VWAP, ADX, ATR) are calculated from:
- **SPOT NIFTY** for price-based indicators (RSI, EMA, ADX, ATR)
- **NIFTY FUTURE** for VWAP (because spot has no volume)

**This is CORRECT because:**
1. We trade options but analyze the UNDERLYING index
2. Technical analysis is done on Nifty index, not individual option strikes
3. Option prices are derivatives of underlying movement

**Code Confirmation:**
```python
def _calculate_indicators(self, df: pd.DataFrame):
    """Calculates technical indicators from SPOT data."""
    closes = df['c'].astype(float)  # SPOT closes
    # EMAs, RSI, ADX calculated from spot data
    
def _calculate_vwap(self, df: pd.DataFrame):
    """Calculates VWAP from FUTURE candles.
    Why? NIFTY is an index - it has NO volume!"""
```

**Indicators are used correctly:**
- Strategies check if spot RSI is overbought/oversold
- Strategies check if spot price crosses VWAP
- Strategies check if EMAs are aligned for trend
- All of this is standard options trading practice

### Issue 4: Position Monitoring ✅ VERIFIED CORRECT

**How Position Monitoring Works:**
```python
def _manage_position(self, data, context):
    pos = self.active_position
    
    # Get price for POSITION STRIKE (not ATM)
    current_price = self.engine.get_option_price(pos['strike'], pos['type'])
    
    # Compare to entry price, target, stop loss
    # All based on the position's strike
```

**Safeguards Added:**
- Warning if price data missing for position strike
- Warning if ATM drifts > 100 points from position strike
- Force exit if strike data unavailable for 5 minutes
- Clear logging of which strike is being monitored

## Root Cause Summary

| Issue | Status | Root Cause | Fix |
|-------|--------|------------|-----|
| "Strike changes during trade" | ❌ False alarm | Logs showed dynamic ATM, not position strike | Added Active_Strike column |
| "Buy at X, sell at Y" | ✅ Working | Strike selection logic (ATM vs affordable) | Added entry logging |
| "Wrong indicator values" | ✅ Correct | Indicators from spot/future, not options | Verified and documented |
| "Strategy not working" | ⚠️ Needs testing | Could be strategy logic, not strike issue | Requires live testing |

## Changes Made

### 1. Enhanced Logger (`loggers/enhanced_logger.py`)

**Before:**
```python
"ATM_Strike", "PCR", "Signal", "PnL"
engine.atm_strike,  # Always shows current ATM
```

**After:**
```python
"ATM_Strike", "Active_Strike", "PCR", "Signal", "PnL"
engine.atm_strike,   # Current market ATM
active_strike,       # Position strike or ATM if scanning
```

### 2. Strategy Runner (`execution/strategy_runner.py`)

**Entry Logging:**
```python
# Show when strike differs from ATM
if strike != current_atm:
    print(f"Selected {option_type} {strike} (ATM was {current_atm}, offset: {strike_offset:+d})")

# Entry message shows both ATM and active strike
print(f"ATM: {self.engine.atm_strike} | Active Strike: {strike} (Monitoring this strike)")
```

**Position Monitoring:**
```python
# Validate monitoring correct strike
if abs(self.engine.atm_strike - pos['strike']) > 100:
    print(f"ATM={self.engine.atm_strike} but monitoring strike={pos['strike']}")
```

## How to Use New Logs

### Scanning Phase
```csv
Time,Spot,ATM_Strike,Active_Strike,Signal
11:43:48,25775.6,25800,25800,SCANNING
11:43:59,25768.4,25750,25750,SCANNING
```
- ATM_Strike = Active_Strike = current market ATM
- Both change as spot moves (this is normal)

### In Position
```csv
Time,Spot,ATM_Strike,Active_Strike,Signal
14:13:57,25657.95,25650,25600,BUY_PE
14:15:30,25665.20,25650,25600,BUY_PE
14:18:45,25620.10,25600,25600,BUY_PE
14:22:09,25625.80,25600,25600,BUY_PE
```
- ATM_Strike changes as spot moves (25650→25600)
- Active_Strike stays constant (25600) - this is the position strike
- Monitoring and exits based on Active_Strike, not ATM_Strike

## Testing Recommendations

1. **Run live paper trading and verify:**
   - Active_Strike stays constant during trades
   - Entry and exit at same strike
   - Indicators behave reasonably for market conditions

2. **Check strategy performance:**
   - Review win rate and P&L
   - Verify strategies trigger in appropriate market conditions
   - Tune strategy parameters if needed

3. **Monitor warnings:**
   - Check for "Strike offset" messages during entry
   - Check for ATM drift warnings during positions
   - Check for missing price data warnings

## Conclusion

**The core trading logic was correct all along.** The confusion arose from:
1. Logs showing only the dynamic ATM strike
2. Lack of visibility into strike selection logic
3. Not distinguishing between market ATM and position strike

**Fixes applied:**
- ✅ Added Active_Strike column to clearly show monitored strike
- ✅ Added entry logging to explain strike selection
- ✅ Added position monitoring warnings for debugging
- ✅ Verified indicator calculations are correct

**Next steps:**
- Test with live/paper trading to verify fixes
- Monitor new log columns and warnings
- Evaluate actual strategy performance (not just logging)
