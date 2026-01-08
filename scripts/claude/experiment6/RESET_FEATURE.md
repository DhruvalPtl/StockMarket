# Auto-Reset on Max Daily Loss Feature

## Overview
Your bot now automatically resets and continues trading when max daily loss is hit - no need to manually restart the code!

## What's New

### 1. **Auto-Reset Mechanism**
- Bot monitors daily P&L continuously
- When loss exceeds max daily loss limit (₹5000), auto-reset triggers
- System logs the event and starts fresh with new capital
- No manual intervention required

### 2. **Comprehensive Logging System**
- All live trading activity logged to timestamped files
- Location: `logs/Live_System_Log_YYYYMMDD_HHMMSS.txt`
- Logs include:
  - System initialization
  - Trade entries/exits
  - Reset events with detailed stats
  - Errors and warnings
  - Market data updates

### 3. **Reset Process**
When max loss hit:
1. ✅ Force exit all open positions
2. ✅ Log previous session stats (Loss, Trades, Win Rate)
3. ✅ Reset Risk Manager (fresh capital)
4. ✅ Reset Signal Aggregator
5. ✅ Clear all strategy statistics
6. ✅ Wait 5 seconds
7. ✅ Resume trading with fresh capital

## Configuration

In [config.py](config.py):
```python
class Risk:
    CAPITAL_PER_STRATEGY = 10000  # Fresh capital per reset
    MAX_DAILY_LOSS = 5000         # Loss limit before reset
    MAX_DAILY_LOSS_ACTION = "LOG" # Change to "HALT" to stop instead
```

## Reset Log Example
```
============================================================
🔄 AUTO-RESET #1 - MAX DAILY LOSS HIT
Previous Loss: ₹5,250.00
Trades Taken: 15
Win Rate: 40.0%
Starting Fresh Session with Capital: ₹10,000.00
============================================================
⏳ Waiting 5 seconds before resuming...
✅ Fresh session started - ready to trade!
```

## Testing
All 22 tests passing ✅
- Logging system initialized
- Reset mechanism ready
- Real market data flowing

## Benefits
✅ No manual restarts needed
✅ Test bot behavior like real money management
✅ Full audit trail in logs
✅ Automatic recovery from max loss
✅ Continuous operation during market hours

## Files Modified
1. [orchestrator.py](orchestrator.py) - Added logging & reset logic
2. [risk_manager.py](execution/risk_manager.py) - Added reset_daily_stats()
3. [signal_aggregator.py](execution/signal_aggregator.py) - Added reset_stats()

---
**Ready for live testing!** 🚀
