"""
MAIN ENTRY POINT
Run this file to start the entire Multi-Timeframe Trading System.

Usage:
    python main.py
"""

import sys
import os
import time
from datetime import datetime

# 1. Environment Setup: Add current directory to path
# This prevents "ModuleNotFoundError" if run from outside the folder
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 2. Import Orchestrator
try:
    from config import BotConfig
    from multi_timeframe_bot import MultiTimeframeOrchestrator
except ImportError as e:
    print(f"\n❌ CRITICAL IMPORT ERROR: {e}")
    print("   Ensure all 7 previous files are in the same directory.")
    sys.exit(1)

def print_banner():
    """Prints a cool startup banner."""
    print("\n" + "="*60)
    print("""
    ███╗   ███╗██╗   ██╗██╗  ████████╗██╗    ████████╗███████╗
    ████╗ ████║██║   ██║██║  ╚══██╔══╝██║    ╚══██╔══╝██╔════╝
    ██╔████╔██║██║   ██║██║     ██║   ██║       ██║   █████╗  
    ██║╚██╔╝██║██║   ██║██║     ██║   ██║       ██║   ██╔══╝  
    ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║       ██║   ██║     
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝       ╚═╝   ╚═╝     
    
    NIFTY OPTIONS ALGO BOT - Multi-Timeframe Edition v4.0
    """)
    print("="*60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

def main():
    """Main execution function."""
    
    # 1. Show Banner
    print_banner()
    
    # 2. Configuration Summary
    print("\n⚠️  SYSTEM CONFIGURATION:")
    print("-" * 30)
    print(f"📊 Timeframes:   {len(BotConfig.TIMEFRAMES)} {BotConfig.TIMEFRAMES}")
    print(f"🧠 Strategies:   {len(BotConfig.STRATEGIES_TO_RUN)} {BotConfig.STRATEGIES_TO_RUN}")
    print(f"💰 Capital:      Rs.{BotConfig.CAPITAL_PER_STRATEGY:,.0f} per instance")
    print(f"⚡ Total Bots:   {len(BotConfig.TIMEFRAMES) * len(BotConfig.STRATEGIES_TO_RUN)} running in parallel")
    print("-" * 30)
    print("📝 MODE: PAPER TRADING (No real money will be used)")
    print("-" * 30 + "\n")
    
    # 3. Safety Confirmation
    try:
        response = input("🚀 Ready to launch? (Type 'yes' to start): ").strip().lower()
        if response not in ['yes', 'y']:
            print("\n❌ Launch Cancelled.")
            return
    except KeyboardInterrupt:
        print("\n\n❌ Launch Cancelled.")
        return
    
    print("\nInitializing Systems...\n")
    time.sleep(1)
    
    # 4. Launch Orchestrator
    try:
        orchestrator = MultiTimeframeOrchestrator()
        orchestrator.run()
    
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✅ System Shutdown Complete.")
    print(f"📂 Check logs at: {BotConfig.BASE_LOG_PATH}\n")

if __name__ == "__main__":
    main()