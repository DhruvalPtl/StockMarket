"""
NIFTY OPTIONS BACKTEST RUNNER v2.0
==================================
Current Date: 2025-12-27

Two modes: 
1.LOAD_CSV - Use existing CSV file (faster, no API calls)
2.DOWNLOAD_FRESH - Fetch new data from Groww API

Switch between modes using the MODE variable below.
"""

import os
import sys
from datetime import datetime, timedelta

# Import backtester
from claude_nifty_groww_backtester_v3 import NiftyGrowwBacktester, BacktestConfig


# ============================================================
# CONFIGURATION - EDIT THIS SECTION
# ============================================================

# MODE SELECTION:  Choose one
# "LOAD_CSV"       - Load data from existing CSV file
# "DOWNLOAD_FRESH" - Download fresh data from Groww API

MODE = "LOAD_CSV"  # <-- CHANGE THIS TO SWITCH MODES

# Your Groww API credentials (only needed for DOWNLOAD_FRESH mode)
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

# CSV file path (for LOAD_CSV mode)
CSV_FILE_PATH = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv"  # <-- Your CSV path

# Date range for downloading (for DOWNLOAD_FRESH mode)
# Current date: 2025-12-27
DOWNLOAD_START_DATE = "2025-11-24"  # 1 month back
DOWNLOAD_END_DATE = "2025-12-27"    # Today
SAVE_DOWNLOADED_DATA = True
DOWNLOAD_SAVE_PATH = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_downloaded_data.csv"

# Output paths
OUTPUT_DIR = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\results"
TRADES_FILE = f"{OUTPUT_DIR}\\trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
EQUITY_FILE = f"{OUTPUT_DIR}\\equity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
CHARTS_DIR = f"{OUTPUT_DIR}\\charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ============================================================
# STRATEGY CONFIGURATION (Matching your live bot)
# ============================================================

config = BacktestConfig(
    # Capital & Risk
    initial_capital=50000,
    lot_size=75,
    daily_loss_limit_pct=0.10,  # 10% = ₹1,000
    
    # Entry/Exit (from your bot)
    target_points=10,           # ₹750 profit target
    stop_loss_points=5,         # ₹375 stop loss
    trailing_stop_activation=0.50,  # Activate at 50% profit
    trailing_stop_distance=0.15,    # Trail 15% below peak
    max_hold_minutes=30,
    cooldown_seconds=60,
    
    # Strategy parameters
    bullish_rsi_min=55,
    bullish_rsi_max=75,
    bearish_rsi_min=25,
    bearish_rsi_max=45,
    bullish_pcr_threshold=1.1,
    bearish_pcr_threshold=0.9,
    min_signals_required=3,
    
    # Indicators
    rsi_period=14,
    ema_fast=5,
    ema_slow=13,
    rsi_warmup_candles=15,
    
    # Transaction costs
    brokerage_per_trade=20.0,   # ₹20 per trade (entry + exit = ₹40)
    slippage_points=0.5         # 0.5 points slippage
)


# ============================================================
# MAIN EXECUTION
# ============================================================

def run_backtest():
    """Main function to run backtest based on selected mode"""
    
    print("\n" + "=" * 70)
    print("🚀 NIFTY OPTIONS BACKTESTER v2.0")
    print(f"📅 Current Date:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize backtester based on mode
    if MODE == "DOWNLOAD_FRESH": 
        print(f"\n📡 MODE: DOWNLOAD_FRESH")
        print(f"   Fetching data from Groww API...")
        print(f"   Date range: {DOWNLOAD_START_DATE} to {DOWNLOAD_END_DATE}")
        
        bt = NiftyGrowwBacktester(
            api_key=API_KEY,
            api_secret=API_SECRET,
            config=config
        )
        
        # Download data
        df = bt.fetch_historical_data(
            start_date=DOWNLOAD_START_DATE,
            end_date=DOWNLOAD_END_DATE,
            save_path=DOWNLOAD_SAVE_PATH if SAVE_DOWNLOADED_DATA else None
        )
        
    elif MODE == "LOAD_CSV": 
        print(f"\n📂 MODE: LOAD_CSV")
        print(f"   Loading from: {CSV_FILE_PATH}")
        
        # Check if file exists
        if not os.path.exists(CSV_FILE_PATH):
            print(f"\n❌ ERROR: CSV file not found!")
            print(f"   Path: {CSV_FILE_PATH}")
            print(f"\n   Please either:")
            print(f"   1.Update CSV_FILE_PATH to your data file")
            print(f"   2.Switch MODE to 'DOWNLOAD_FRESH' to fetch new data")
            sys.exit(1)
        
        # Initialize without API (not needed for CSV mode)
        bt = NiftyGrowwBacktester(config=config)
        
        # Load data
        df = bt.load_data(CSV_FILE_PATH)
        
    else:
        print(f"\n❌ ERROR: Invalid MODE '{MODE}'")
        print("   Valid options: 'LOAD_CSV' or 'DOWNLOAD_FRESH'")
        sys.exit(1)
    
    # Validate data
    if df is None or len(df) == 0:
        print("\n❌ ERROR: No data loaded!")
        sys.exit(1)
    
    print(f"\n📊 Data Summary:")
    print(f"   Total candles: {len(df):,}")
    print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"   Trading days: {df['datetime'].dt.date.nunique()}")
    
    # Prepare indicators
    print("\n⚙️ Calculating indicators...")
    df = bt.prepare_indicators(df)
    
    # Show indicator sample
    print(f"\n📈 Indicator Sample (last 5 rows):")
    print(df[['datetime', 'close', 'rsi', 'vwap', 'ema5', 'ema13', 'pcr']].tail())
    
    # Run backtest
    print("\n" + "=" * 70)
    print("🏃 RUNNING BACKTEST...")
    print("=" * 70)
    
    results = bt.run(df, verbose=True)
    
    # Debug: Check why no trades
    print(f"\n🔍 DEBUG - Why no trades? ")
    tradeable = df[df['rsi_ready'] & df['in_market']]
    print(f"   Tradeable candles: {len(tradeable)}")

    # Check conditions
    sample = tradeable.iloc[100:110] if len(tradeable) > 110 else tradeable.head(10)
    for idx, row in sample.iterrows():
        spot = row['close']
        vwap = row['vwap']
        rsi = row['rsi']
        
        above_vwap = spot > vwap
        below_vwap = spot < vwap
        rsi_bullish = 55 <= rsi <= 75
        rsi_bearish = 25 <= rsi <= 45
        
        print(f"   {row['datetime']} | Spot: {spot:.0f} | VWAP: {vwap:.0f} | RSI: {rsi:.1f} | "
            f"Above VWAP:  {above_vwap} | RSI Bullish:  {rsi_bullish} | RSI Bearish: {rsi_bearish}")
    
    # Print results
    bt.print_results()
    
    # Export results
    print("\n📁 Exporting Results...")
    bt.export_trades(TRADES_FILE)
    bt.export_equity(EQUITY_FILE)
    
    # Generate charts
    print("\n📊 Generating Charts...")
    bt.plot_results(CHARTS_DIR)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ BACKTEST COMPLETE!")
    print("=" * 70)
    print(f"\n📂 Output Files:")
    print(f"   Trades:   {TRADES_FILE}")
    print(f"   Equity:   {EQUITY_FILE}")
    print(f"   Charts:  {CHARTS_DIR}/")
    
    # Quick stats
    print(f"\n📊 Quick Summary:")
    print(f"   Total Return: {results['total_return_pct']:+.2f}%")
    print(f"   Win Rate: {results['win_rate']:.1f}%")
    print(f"   Profit Factor: {results['profit_factor']:.2f}")
    print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"   Total Trades: {results['total_trades']}")
    
    return bt, results


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__": 
    bt, results = run_backtest()