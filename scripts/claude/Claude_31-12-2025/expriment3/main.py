"""
MAIN ENTRY POINT - Run this file to start the multi-timeframe bot

Single command to test all strategies across all timeframes simultaneously:
    python main.py

This will run:
- 4 timeframes (1min, 2min, 3min, 5min)
- 4 strategies per timeframe (ORIGINAL, A, B, C)
- Total: 16 parallel tests in one execution

All results saved to separate CSV files per strategy-timeframe combination.
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multi_timeframe_bot import MultiTimeframeOrchestrator
from config import BotConfig


def print_banner():
    """Print startup banner"""
    print("\n" + "="*80)
    print("""
    ███╗   ███╗██╗   ██╗██╗  ████████╗██╗    ████████╗███████╗
    ████╗ ████║██║   ██║██║  ╚══██╔══╝██║    ╚══██╔══╝██╔════╝
    ██╔████╔██║██║   ██║██║     ██║   ██║       ██║   █████╗  
    ██║╚██╔╝██║██║   ██║██║     ██║   ██║       ██║   ██╔══╝  
    ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║       ██║   ██║     
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝       ╚═╝   ╚═╝     
    
    NIFTY OPTIONS ALGO BOT - Multi-Timeframe Edition v4.0
    """)
    print("="*80)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
    print("="*80 + "\n")


def main():
    """Main execution function"""
    
    # Print banner
    print_banner()
    
    # Safety confirmation
    print("\n⚠️  IMPORTANT INFORMATION:")
    print("="*80)
    print("📊 This bot will run multiple strategies across multiple timeframes.")
    print(f"🔢 Total test combinations: {len(BotConfig.TIMEFRAMES)} timeframes × {len(BotConfig.STRATEGIES_TO_RUN)} strategies")
    print(f"   = {len(BotConfig.TIMEFRAMES) * len(BotConfig.STRATEGIES_TO_RUN)} parallel tests")
    print("\n💰 PAPER TRADING MODE - No real money at risk")
    print("📝 All trades logged to separate CSV files")
    print("\n🛑 Press Ctrl+C to stop at any time")
    print("="*80 + "\n")
    
    # User confirmation
    try:
        response = input("Ready to start? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("\n❌ Cancelled by user")
            return
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        return
    
    print("\n")
    
    # Initialize and run orchestrator
    try:
        orchestrator = MultiTimeframeOrchestrator()
        orchestrator.run()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Shutting down gracefully...")
    
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✅ Bot execution completed")
    print("📊 Check CSV files for detailed results\n")


if __name__ == "__main__":
    main()
