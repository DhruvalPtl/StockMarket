"""
EXAMPLE USAGE - Flate Trade API Integration
===========================================
This file demonstrates how to use the unified API integration
with both Groww and Flate Trade.

Author: Claude
Date: 2026-01-06
"""

# ============================================================
# EXAMPLE 1: Basic API Usage
# ============================================================

def example_1_basic_usage():
    """Show basic usage with both providers"""
    from unified_api import UnifiedAPI
    from config import BotConfig
    from datetime import datetime, timedelta
    
    print("=" * 60)
    print("EXAMPLE 1: Basic API Usage")
    print("=" * 60)
    
    # Method 1: Use Groww
    print("\n1️⃣ Using Groww API:")
    api_groww = UnifiedAPI(
        provider="groww",
        api_key=BotConfig.GROWW_API_KEY,
        api_secret=BotConfig.GROWW_API_SECRET
    )
    
    # Method 2: Use Flate Trade (same code!)
    print("\n2️⃣ Using Flate Trade API:")
    api_flate = UnifiedAPI(
        provider="flate",
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN
    )
    
    # Both work identically!
    end = datetime.now()
    start = end - timedelta(hours=1)
    
    print("\n📊 Fetching historical candles (last 1 hour)...")
    
    for name, api in [("Groww", api_groww), ("Flate", api_flate)]:
        candles = api.get_historical_candles(
            "NSE", "CASH", "NSE-NIFTY",
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
            "5minute"
        )
        
        if candles and 'candles' in candles:
            print(f"   {name}: {len(candles['candles'])} candles")
        else:
            print(f"   {name}: No data")


# ============================================================
# EXAMPLE 2: Migrating Existing Code
# ============================================================

def example_2_migration():
    """Show how to migrate existing Groww code"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Migration from Groww API")
    print("=" * 60)
    
    # BEFORE (Old Groww code):
    print("\n❌ OLD CODE (Groww only):")
    print("""
    from growwapi import GrowwAPI
    
    token = GrowwAPI.get_access_token(api_key=KEY, secret=SECRET)
    groww = GrowwAPI(token)
    
    candles = groww.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    ltp = groww.get_ltp("NSE", "NSE-NIFTY", "CASH")
    """)
    
    # AFTER (Works with both!):
    print("\n✅ NEW CODE (Works with both Groww and Flate):")
    print("""
    from unified_api import UnifiedAPI
    
    # Just change this one line to switch providers!
    api = UnifiedAPI(provider="groww", api_key=KEY, api_secret=SECRET)
    # api = UnifiedAPI(provider="flate", user_id=UID, user_token=TOKEN)
    
    # All existing code works unchanged!
    candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    ltp = api.get_ltp("NSE", "NSE-NIFTY", "CASH")
    """)


# ============================================================
# EXAMPLE 3: Data Pipeline
# ============================================================

def example_3_data_pipeline():
    """Show data pipeline usage"""
    from data_pipeline import UnifiedDataEngine
    from config import BotConfig, get_future_symbol
    import time
    
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Data Pipeline")
    print("=" * 60)
    
    # Calculate future symbol
    fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
    
    print("\n🔧 Creating data engine...")
    print(f"   Provider: Groww")
    print(f"   Expiry: {BotConfig.OPTION_EXPIRY}")
    print(f"   Future: {fut_symbol}")
    
    # Create engine
    engine = UnifiedDataEngine(
        provider="groww",
        api_key=BotConfig.GROWW_API_KEY,
        api_secret=BotConfig.GROWW_API_SECRET,
        expiry_date=BotConfig.OPTION_EXPIRY,
        fut_symbol=fut_symbol
    )
    
    # Run a few updates
    print("\n📊 Running 3 updates...")
    for i in range(3):
        print(f"\nUpdate {i+1}:")
        engine.update()
        
        # Access the data
        print(f"   Nifty Spot: {engine.spot_ltp:.2f}")
        print(f"   RSI: {engine.rsi:.1f}")
        print(f"   VWAP: {engine.vwap:.2f}")
        print(f"   ATM Strike: {engine.atm_strike}")
        print(f"   PCR: {engine.pcr:.2f}")
        
        if i < 2:
            time.sleep(10)
    
    # Health check
    print("\n🏥 Health Status:")
    health = engine.get_health_status()
    for key, value in health.items():
        print(f"   {key}: {value}")


# ============================================================
# EXAMPLE 4: Option Fetcher
# ============================================================

def example_4_option_fetcher():
    """Show option fetcher usage"""
    from option_fetcher import UnifiedOptionFetcher
    from config import BotConfig
    from datetime import datetime
    
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Option Fetcher")
    print("=" * 60)
    
    print("\n🔧 Creating option fetcher...")
    fetcher = UnifiedOptionFetcher(
        provider="groww",
        api_key=BotConfig.GROWW_API_KEY,
        api_secret=BotConfig.GROWW_API_SECRET
    )
    
    # Get expiry
    today = datetime.now()
    expiry = fetcher.get_expiry_for_date(today)
    print(f"\n📅 Next expiry: {expiry}")
    
    # Fetch option data
    strike = 24000
    option_type = "CE"
    
    print(f"\n📊 Fetching {strike} {option_type} data...")
    data = fetcher.fetch_option_data(strike, option_type, today, expiry)
    
    if data is not None and len(data) > 0:
        print(f"✅ Got {len(data)} candles")
        print(f"   First: {data['datetime'].iloc[0]}")
        print(f"   Last:  {data['datetime'].iloc[-1]}")
        print(f"   Close: {data['close'].iloc[-1]:.2f}")
    else:
        print("⚠️ No data available")
    
    # Get LTP
    ltp = fetcher.get_ltp(strike, option_type, expiry)
    print(f"\n💰 Current LTP: ₹{ltp:.2f}")
    
    # Statistics
    print("\n📊 Fetcher Stats:")
    stats = fetcher.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


# ============================================================
# EXAMPLE 5: Trading Bot Integration
# ============================================================

def example_5_trading_bot():
    """Show how a trading bot would use the unified API"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Trading Bot Integration")
    print("=" * 60)
    
    print("\n📝 Example Trading Bot Code:")
    print("""
    from unified_api import UnifiedAPI
    from config import BotConfig
    
    # Initialize API (switch provider here!)
    api = UnifiedAPI(provider="groww", api_key=KEY, api_secret=SECRET)
    
    # Your existing trading logic
    while True:
        # Get spot price
        spot_data = api.get_ltp("NSE", "NSE-NIFTY", "CASH")
        spot_ltp = spot_data['ltp']
        
        # Calculate ATM
        atm_strike = round(spot_ltp / 50) * 50
        
        # Get option LTP
        ce_symbol = f"NSE-NIFTY-06Jan26-{atm_strike}-CE"
        ce_ltp_data = api.get_ltp("NSE", ce_symbol, "FNO")
        ce_ltp = ce_ltp_data['ltp']
        
        # Your strategy logic
        if should_enter_trade(spot_ltp, ce_ltp):
            # Place order
            api.place_order(
                exchange="NSE",
                symbol=ce_symbol,
                transaction_type="BUY",
                quantity=75,
                order_type="MARKET"
            )
        
        time.sleep(30)
    """)
    
    print("\n💡 Key Points:")
    print("   - Same code works with both Groww and Flate Trade")
    print("   - Just change provider parameter to switch")
    print("   - No other code changes needed!")


# ============================================================
# EXAMPLE 6: Comparison Testing
# ============================================================

def example_6_comparison():
    """Show comparison testing"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 6: API Comparison")
    print("=" * 60)
    
    print("\n📝 Run comparison test:")
    print("""
    python test_comparison.py
    """)
    
    print("\n📊 This will:")
    print("   1. Connect to both Groww and Flate Trade")
    print("   2. Fetch historical candles from both")
    print("   3. Fetch LTP from both")
    print("   4. Fetch option chain from both")
    print("   5. Compare results side-by-side")
    print("   6. Flag any discrepancies")
    print("   7. Print detailed report")
    
    print("\n✅ Expected Output:")
    print("""
    ✅ Groww API connected
    ✅ Flate Trade API connected
    
    📊 COMPARING HISTORICAL CANDLES
    ✅ Got 24 candles (Groww)
    ✅ Got 24 candles (Flate)
    📈 COMPARISON: ✅ MATCH
    
    Match Rate: 2/2 (100.0%)
    ✅ GOOD - APIs are producing consistent results
    """)


# ============================================================
# MAIN MENU
# ============================================================

def main():
    """Main menu"""
    print("\n" + "=" * 60)
    print("🚀 FLATE TRADE API INTEGRATION - EXAMPLES")
    print("=" * 60)
    
    print("\nAvailable Examples:")
    print("1. Basic API Usage")
    print("2. Migration from Groww")
    print("3. Data Pipeline")
    print("4. Option Fetcher")
    print("5. Trading Bot Integration")
    print("6. Comparison Testing")
    
    print("\n" + "=" * 60)
    print("NOTE: These are code examples, not live tests.")
    print("To run live tests, use:")
    print("  - python test_comparison.py")
    print("  - python data_pipeline.py --api groww")
    print("  - python option_fetcher.py --api groww")
    print("=" * 60)
    
    # Show all examples
    example_1_basic_usage()
    example_2_migration()
    # example_3_data_pipeline()  # Commented out - requires API connection
    # example_4_option_fetcher()  # Commented out - requires API connection
    example_5_trading_bot()
    example_6_comparison()
    
    print("\n✅ Examples complete!")
    print("\n💡 Next Steps:")
    print("   1. Add your API credentials to config.py")
    print("   2. Run: python test_comparison.py")
    print("   3. Test: python data_pipeline.py --api groww --updates 3")
    print("   4. Switch to Flate Trade and test again!")


if __name__ == "__main__":
    main()
