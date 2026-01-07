"""
EXAMPLE USAGE - Flattrade API Integration
==========================================
This file demonstrates how to use the Flattrade API integration.

Author: Claude
Date: 2026-01-06
"""

# ============================================================
# EXAMPLE 1: Basic API Usage
# ============================================================

def example_1_basic_usage():
    """Show basic usage with Flattrade"""
    from unified_api import UnifiedAPI
    from config import BotConfig
    from datetime import datetime, timedelta
    
    print("=" * 60)
    print("EXAMPLE 1: Basic API Usage with Flattrade")
    print("=" * 60)
    
    # Initialize Flattrade API
    print("\n1️⃣ Using Flattrade API:")
    api = UnifiedAPI(
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN
    )
    
    # Fetch historical data
    end = datetime.now()
    start = end - timedelta(hours=1)
    
    print("\n📊 Fetching historical candles (last 1 hour)...")
    
    candles = api.get_historical_candles(
        "NSE", "CASH", "NSE-NIFTY",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
        "5minute"
    )
    
    if candles and 'candles' in candles:
        print(f"   Flattrade: {len(candles['candles'])} candles received")
        print(f"   Latest close: {candles['candles'][-1]['c']}")
    else:
        print(f"   No data received")


# ============================================================
# EXAMPLE 2: Using the Wrapper Directly
# ============================================================

def example_2_direct_wrapper():
    """Show how to use FlattradeWrapper directly"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Using FlattradeWrapper Directly")
    print("=" * 60)
    
    # Direct usage of the wrapper
    print("\n✅ NEW CODE (Flattrade):")
    print("""
    from utils.flattrade_wrapper import FlattradeWrapper
    from config import BotConfig
    
    api = FlattradeWrapper(
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN
    )
    
    candles = api.get_historical_candles("NSE", "CASH", "NSE-NIFTY", start, end, "1minute")
    ltp = api.get_quote("NSE-NIFTY")
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
    print("EXAMPLE 3: Data Pipeline with Flattrade")
    print("=" * 60)
    
    # Calculate future symbol
    fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
    
    print("\n🔧 Creating data engine...")
    print(f"   Provider: Flattrade")
    print(f"   Expiry: {BotConfig.OPTION_EXPIRY}")
    print(f"   Future: {fut_symbol}")
    
    # Create engine
    engine = UnifiedDataEngine(
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN,
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
    print("EXAMPLE 4: Option Fetcher with Flattrade")
    print("=" * 60)
    
    print("\n🔧 Creating option fetcher...")
    fetcher = UnifiedOptionFetcher(
        user_id=BotConfig.USER_ID,
        user_token=BotConfig.USER_TOKEN
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
    """Show how a trading bot would use the Flattrade API"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Trading Bot Integration with Flattrade")
    print("=" * 60)
    
    print("\n📝 Example Trading Bot Code:")
    print("""
    from unified_api import UnifiedAPI
    from config import BotConfig
    
    # Initialize Flattrade API
    api = UnifiedAPI(user_id=BotConfig.USER_ID, user_token=BotConfig.USER_TOKEN)
    
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
    print("   - Uses Flattrade API for all operations")
    print("   - Direct integration with trading platform")
    print("   - Reliable real-time data and order execution")


# ============================================================
# EXAMPLE 6: Testing
# ============================================================

def example_6_testing():
    """Show testing approach"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Testing Flattrade API")
    print("=" * 60)
    
    print("\n📝 Run test script:")
    print("""
    python test_flattrade_data.py
    """)
    
    print("\n📊 This will:")
    print("   1. Connect to Flattrade")
    print("   2. Fetch last 7 days of NIFTY SPOT data")
    print("   3. Fetch last 7 days of NIFTY FUTURE data")
    print("   4. Save data to CSV files")
    print("   5. Print summary statistics")
    
    print("\n✅ Expected Output:")
    print("""
    ✅ Flattrade Wrapper Connected Successfully!
    
    📊 Fetching NIFTY SPOT data...
    ✓ 2026-01-05: 78 candles
    ✓ 2026-01-06: 82 candles
    ✅ SPOT Data saved: flattrade_spot_test.csv
    
    📊 Fetching NIFTY FUTURES data...
    ✓ 2026-01-05: 78 candles
    ✓ 2026-01-06: 82 candles
    ✅ FUTURE Data saved: flattrade_future_test.csv
    
    ✅ TEST COMPLETE
    """)


# ============================================================
# MAIN MENU
# ============================================================

def main():
    """Main menu"""
    print("\n" + "=" * 60)
    print("🚀 FLATTRADE API INTEGRATION - EXAMPLES")
    print("=" * 60)
    
    print("\nAvailable Examples:")
    print("1. Basic API Usage")
    print("2. Using Wrapper Directly")
    print("3. Data Pipeline")
    print("4. Option Fetcher")
    print("5. Trading Bot Integration")
    print("6. Testing")
    
    print("\n" + "=" * 60)
    print("NOTE: These are code examples, not live tests.")
    print("To run live tests, use:")
    print("  - python test_flattrade_data.py")
    print("  - python data_pipeline.py")
    print("  - python option_fetcher.py")
    print("=" * 60)
    
    # Show all examples
    example_1_basic_usage()
    example_2_direct_wrapper()
    # example_3_data_pipeline()  # Commented out - requires API connection
    # example_4_option_fetcher()  # Commented out - requires API connection
    example_5_trading_bot()
    example_6_testing()
    
    print("\n✅ Examples complete!")
    print("\n💡 Next Steps:")
    print("   1. Add your credentials to config.py (USER_ID, USER_TOKEN)")
    print("   2. Run: python gettoken.py")
    print("   3. Test: python test_flattrade_data.py")
    print("   4. Run your trading bot with Flattrade!")


if __name__ == "__main__":
    main()
