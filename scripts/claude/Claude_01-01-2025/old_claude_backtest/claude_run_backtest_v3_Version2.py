"""
RUN BACKTEST V3
===============
Uses real option data from Groww API

Author: Claude
Date: 2025-12-27
"""

import pandas as pd
import os
from datetime import datetime

from claude_nifty_groww_backtester_v3 import ClaudeNiftyGrowwBacktesterV3, BacktestConfigV3


def run_backtest():
    """Run backtest with real option data"""
    
    print("\n" + "=" * 70)
    print("🚀 NIFTY OPTIONS BACKTESTER V3 (Real Option Data)")
    print(f"📅 Current Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # ========================================
    # CONFIGURATION
    # ========================================
    
    # Groww API credentials
    API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
    API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"
    
    # Data file path
    CSV_FILE_PATH = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\data\\nifty_complete_1min.csv"
    
    # Results directory
    RESULTS_DIR = "D:\\StockMarket\\StockMarket\\scripts\\claude\\claude_backtest\\results_v3"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # ========================================
    # LOAD DATA
    # ========================================
    
    print(f"\n📂 Loading:  {CSV_FILE_PATH}")
    
    df = pd.read_csv(CSV_FILE_PATH)
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    print(f"✅ Loaded {len(df):,} candles")
    print(f"   Range: {df['datetime'].min()} to {df['datetime'].max()}")
    
    # ========================================
    # CREATE CONFIG
    # ========================================
    
    config = BacktestConfigV3(
        # Capital
        initial_capital=50000.0,
        lot_size=75,
        
        # Option price limits
        min_option_price=30.0,
        max_capital_per_trade=0.95,
        
        # Entry conditions - RELAXED (BEST PERFORMER)
        min_signals_required=3,
        bullish_rsi_min=50.0,  # Relaxed
        bullish_rsi_max=75.0,
        bearish_rsi_min=25.0,
        bearish_rsi_max=50.0,  # Relaxed
        bullish_pcr_threshold=1.05,
        bearish_pcr_threshold=0.95,
        
        # Exit conditions
        target_points=12.0,
        stop_loss_points=8.0,  # Tighter than 10
        trailing_trigger_pct=0.06,
        trailing_stop_pct=0.12,
        max_hold_minutes=45,
        
        # Cooldown
        cooldown_seconds=120,
        
        # Risk
        daily_loss_limit_pct=0.15,
        
        # PCR
        pcr_strikes_range=10,
    )
    
    # ========================================
    # CREATE BACKTESTER
    # ========================================
    
    print("\n⚙️ Initializing backtester...")
    
    bt = ClaudeNiftyGrowwBacktesterV3(
        config=config,
        api_key=API_KEY,
        api_secret=API_SECRET,
        debug=True
    )
    
    # ========================================
    # PREPARE DATA
    # ========================================
    
    print("\n⚙️ Preparing indicators...")
    df = bt.prepare_indicators(df)
    
    print(f"\n📈 Data Sample (last 5 rows):")
    print(df[['datetime', 'close', 'fut_close', 'vwap', 'rsi', 'ema5', 'ema13', 'atm_strike']].tail().to_string())
    
    # ========================================
    # RUN BACKTEST
    # ========================================
    
    print("\n" + "=" * 70)
    print("🏃 RUNNING BACKTEST...")
    print("=" * 70)
    
    results = bt.run(df, verbose=True)
    
    # ========================================
    # PRINT RESULTS
    # ========================================
    
    bt.print_results()
    
    # ========================================
    # EXPORT RESULTS
    # ========================================
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    trades_file = os.path.join(RESULTS_DIR, f"trades_v3_{timestamp}.csv")
    equity_file = os.path.join(RESULTS_DIR, f"equity_v3_{timestamp}.csv")
    
    bt.export_trades(trades_file)
    bt.export_equity_curve(equity_file)
    
    # ========================================
    # SUMMARY
    # ========================================
    
    print("\n" + "=" * 70)
    print("✅ BACKTEST V3 COMPLETE!")
    print("=" * 70)
    
    print(f"\n📂 Output Files:")
    print(f"   Trades: {trades_file}")
    print(f"   Equity:  {equity_file}")
    
    print(f"\n📊 Quick Summary:")
    print(f"   Total Return: {results['total_return_pct']:+.2f}%")
    print(f"   Win Rate: {results['win_rate']:.1f}%")
    print(f"   Profit Factor: {results['profit_factor']:.2f}")
    print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   API Calls: {results['api_calls']}")
    
    return bt, results


if __name__ == "__main__":
    bt, results = run_backtest()