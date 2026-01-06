# Quick Setup Guide

## ⚡ 5-Minute Setup

### Step 1: Navigate to Directory
```bash
cd scripts/claude/expriment6/flatetrade
```

### Step 2: Add Your Credentials

Open `config.py` and update:

```python
# Groww API Credentials
GROWW_API_KEY = "YOUR_GROWW_API_KEY_HERE"
GROWW_API_SECRET = "YOUR_GROWW_API_SECRET_HERE"

# Flate Trade Credentials  
USER_ID = "YOUR_FLATE_TRADE_USER_ID"
USER_TOKEN = "YOUR_FLATE_TRADE_TOKEN"
```

### Step 3: Test Connection

```bash
# Test with Groww
python test_comparison.py
```

If successful, you'll see:
```
✅ Groww API connected
✅ Flate Trade API connected
📊 COMPARING HISTORICAL CANDLES...
```

### Step 4: Run Data Pipeline

```bash
# Use Groww (default)
python data_pipeline.py --api groww --updates 3

# Or use Flate Trade
python data_pipeline.py --api flate --updates 3
```

### Step 5: Migrate Your Bots

Update your existing code:

**Before:**
```python
from growwapi import GrowwAPI
groww = GrowwAPI(token)
```

**After:**
```python
from unified_api import UnifiedAPI
api = UnifiedAPI(provider="groww", api_key=key, api_secret=secret)
# OR: api = UnifiedAPI(provider="flate", user_id=uid, user_token=token)
```

That's it! 🎉

---

## 📋 Checklist

- [ ] Credentials added to `config.py`
- [ ] `test_comparison.py` runs successfully
- [ ] Data pipeline works with Groww
- [ ] Data pipeline works with Flate Trade
- [ ] Existing bots migrated to `UnifiedAPI`
- [ ] Tested switching between providers

---

## 🆘 Common Issues

### "Module not found"
```bash
pip install pandas numpy growwapi
```

### "Connection failed"
- Check credentials in `config.py`
- Verify token hasn't expired
- For Groww: Regenerate token if needed
- For Flate Trade: Get new token from login flow

### "No data received"
- Check if market is open (9:15 AM - 3:30 PM IST)
- Verify symbol format is correct
- Check date/time range

---

## 📚 Next Steps

1. Read full documentation: [README.md](README.md)
2. Review examples: [examples.py](examples.py)
3. Test comparison: `python test_comparison.py`
4. Start trading! 🚀

---

## 💡 Pro Tips

- Use `--updates 1` for quick tests
- Check logs in `log/engine_logs/` folder
- Run comparison test before production use
- Monitor both APIs for consistency
- Keep tokens secure - never commit to Git

---

**Happy Trading! 📈**
