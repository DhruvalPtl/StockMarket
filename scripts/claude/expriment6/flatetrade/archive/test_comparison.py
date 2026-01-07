"""
API COMPARISON TEST
===================
Tests both Groww and Flate Trade APIs side-by-side and compares results.

Features:
- Compares historical candles (spot prices)
- Compares option chain data
- Compares LTP prices
- Prints side-by-side comparison table
- Flags discrepancies

Usage:
    python test_comparison.py

Author: Claude
Date: 2026-01-06
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys

# Import unified API
try:
    from unified_api import UnifiedAPI
    from config import BotConfig
except ImportError:
    from .unified_api import UnifiedAPI
    from .config import BotConfig


class APIComparison:
    """Compare Groww and Flate Trade APIs"""
    
    def __init__(self):
        """Initialize both APIs"""
        print("🔗 Initializing APIs...\n")
        
        # Initialize Groww API
        try:
            self.groww = UnifiedAPI(
                provider="groww",
                api_key=BotConfig.GROWW_API_KEY,
                api_secret=BotConfig.GROWW_API_SECRET
            )
            print("✅ Groww API connected")
        except Exception as e:
            print(f"❌ Groww API failed: {e}")
            self.groww = None
        
        # Initialize Flate Trade API
        try:
            self.flate = UnifiedAPI(
                provider="flate",
                user_id=BotConfig.USER_ID,
                user_token=BotConfig.USER_TOKEN
            )
            print("✅ Flate Trade API connected")
        except Exception as e:
            print(f"❌ Flate Trade API failed: {e}")
            self.flate = None
        
        print()
    
    def compare_historical_candles(self) -> Dict:
        """Compare historical candles from both APIs"""
        print("=" * 80)
        print("📊 COMPARING HISTORICAL CANDLES (NIFTY SPOT)")
        print("=" * 80)
        
        # Setup parameters
        end = datetime.now()
        start = end - timedelta(hours=2)
        
        results = {
            'test': 'Historical Candles',
            'symbol': 'NSE-NIFTY',
            'interval': '5minute',
            'groww': {},
            'flate': {},
            'comparison': {}
        }
        
        # Fetch from Groww
        if self.groww:
            try:
                print("\n🔍 Fetching from Groww...")
                groww_data = self.groww.get_historical_candles(
                    "NSE", "CASH", "NSE-NIFTY",
                    start.strftime("%Y-%m-%d %H:%M:%S"),
                    end.strftime("%Y-%m-%d %H:%M:%S"),
                    "5minute"
                )
                
                if groww_data and 'candles' in groww_data:
                    candles = groww_data['candles']
                    results['groww'] = {
                        'candles_count': len(candles),
                        'first_time': candles[0]['t'] if candles else None,
                        'last_time': candles[-1]['t'] if candles else None,
                        'last_close': candles[-1]['c'] if candles else None,
                        'status': 'SUCCESS'
                    }
                    print(f"✅ Got {len(candles)} candles")
                    print(f"   Last close: {candles[-1]['c']:.2f}")
                else:
                    results['groww']['status'] = 'NO_DATA'
                    print("⚠️ No data received")
                    
            except Exception as e:
                results['groww']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['groww']['status'] = 'NOT_AVAILABLE'
        
        # Fetch from Flate Trade
        if self.flate:
            try:
                print("\n🔍 Fetching from Flate Trade...")
                flate_data = self.flate.get_historical_candles(
                    "NSE", "CASH", "NSE-NIFTY",
                    start.strftime("%Y-%m-%d %H:%M:%S"),
                    end.strftime("%Y-%m-%d %H:%M:%S"),
                    "5minute"
                )
                
                if flate_data and 'candles' in flate_data:
                    candles = flate_data['candles']
                    results['flate'] = {
                        'candles_count': len(candles),
                        'first_time': candles[0]['t'] if candles else None,
                        'last_time': candles[-1]['t'] if candles else None,
                        'last_close': candles[-1]['c'] if candles else None,
                        'status': 'SUCCESS'
                    }
                    print(f"✅ Got {len(candles)} candles")
                    print(f"   Last close: {candles[-1]['c']:.2f}")
                else:
                    results['flate']['status'] = 'NO_DATA'
                    print("⚠️ No data received")
                    
            except Exception as e:
                results['flate']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['flate']['status'] = 'NOT_AVAILABLE'
        
        # Compare
        if (results['groww'].get('status') == 'SUCCESS' and 
            results['flate'].get('status') == 'SUCCESS'):
            
            groww_close = results['groww']['last_close']
            flate_close = results['flate']['last_close']
            
            if groww_close and flate_close:
                diff = abs(groww_close - flate_close)
                diff_pct = (diff / groww_close) * 100
                
                results['comparison'] = {
                    'price_difference': diff,
                    'price_difference_pct': diff_pct,
                    'match': diff_pct < 0.1  # Less than 0.1% difference
                }
                
                print(f"\n📈 COMPARISON:")
                print(f"   Groww: {groww_close:.2f}")
                print(f"   Flate: {flate_close:.2f}")
                print(f"   Diff:  {diff:.2f} ({diff_pct:.3f}%)")
                
                if results['comparison']['match']:
                    print(f"   ✅ MATCH - Prices are very close!")
                else:
                    print(f"   ⚠️ MISMATCH - Significant difference")
        
        return results
    
    def compare_ltp(self) -> Dict:
        """Compare last traded prices"""
        print("\n" + "=" * 80)
        print("💰 COMPARING LAST TRADED PRICE (NIFTY SPOT)")
        print("=" * 80)
        
        results = {
            'test': 'LTP',
            'symbol': 'NSE-NIFTY',
            'groww': {},
            'flate': {},
            'comparison': {}
        }
        
        # Fetch from Groww
        if self.groww:
            try:
                print("\n🔍 Fetching from Groww...")
                groww_ltp = self.groww.get_ltp("NSE", "NSE-NIFTY", "CASH")
                
                if groww_ltp and 'ltp' in groww_ltp:
                    results['groww'] = {
                        'ltp': groww_ltp['ltp'],
                        'status': 'SUCCESS'
                    }
                    print(f"✅ LTP: {groww_ltp['ltp']:.2f}")
                else:
                    results['groww']['status'] = 'NO_DATA'
                    print("⚠️ No data received")
                    
            except Exception as e:
                results['groww']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['groww']['status'] = 'NOT_AVAILABLE'
        
        # Fetch from Flate Trade
        if self.flate:
            try:
                print("\n🔍 Fetching from Flate Trade...")
                flate_ltp = self.flate.get_ltp("NSE", "NSE-NIFTY", "CASH")
                
                if flate_ltp and 'ltp' in flate_ltp:
                    results['flate'] = {
                        'ltp': flate_ltp['ltp'],
                        'status': 'SUCCESS'
                    }
                    print(f"✅ LTP: {flate_ltp['ltp']:.2f}")
                else:
                    results['flate']['status'] = 'NO_DATA'
                    print("⚠️ No data received")
                    
            except Exception as e:
                results['flate']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['flate']['status'] = 'NOT_AVAILABLE'
        
        # Compare
        if (results['groww'].get('status') == 'SUCCESS' and 
            results['flate'].get('status') == 'SUCCESS'):
            
            groww_ltp = results['groww']['ltp']
            flate_ltp = results['flate']['ltp']
            
            if groww_ltp and flate_ltp:
                diff = abs(groww_ltp - flate_ltp)
                diff_pct = (diff / groww_ltp) * 100
                
                results['comparison'] = {
                    'price_difference': diff,
                    'price_difference_pct': diff_pct,
                    'match': diff_pct < 0.1
                }
                
                print(f"\n📈 COMPARISON:")
                print(f"   Groww: {groww_ltp:.2f}")
                print(f"   Flate: {flate_ltp:.2f}")
                print(f"   Diff:  {diff:.2f} ({diff_pct:.3f}%)")
                
                if results['comparison']['match']:
                    print(f"   ✅ MATCH")
                else:
                    print(f"   ⚠️ MISMATCH")
        
        return results
    
    def compare_option_chain(self) -> Dict:
        """Compare option chain data"""
        print("\n" + "=" * 80)
        print("🔗 COMPARING OPTION CHAIN")
        print("=" * 80)
        
        expiry = BotConfig.OPTION_EXPIRY
        
        results = {
            'test': 'Option Chain',
            'expiry': expiry,
            'groww': {},
            'flate': {},
            'comparison': {}
        }
        
        # Fetch from Groww
        if self.groww:
            try:
                print(f"\n🔍 Fetching from Groww (expiry: {expiry})...")
                groww_chain = self.groww.get_option_chain("NSE", "NIFTY", expiry)
                
                if groww_chain and 'strikes' in groww_chain:
                    strikes = groww_chain['strikes']
                    results['groww'] = {
                        'strike_count': len(strikes),
                        'strikes': list(strikes.keys())[:5],  # First 5 strikes
                        'status': 'SUCCESS'
                    }
                    print(f"✅ Got {len(strikes)} strikes")
                else:
                    results['groww']['status'] = 'NO_DATA'
                    print("⚠️ No data received")
                    
            except Exception as e:
                results['groww']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['groww']['status'] = 'NOT_AVAILABLE'
        
        # Fetch from Flate Trade
        if self.flate:
            try:
                print(f"\n🔍 Fetching from Flate Trade (expiry: {expiry})...")
                flate_chain = self.flate.get_option_chain("NSE", "NIFTY", expiry)
                
                if flate_chain and 'strikes' in flate_chain:
                    strikes = flate_chain['strikes']
                    results['flate'] = {
                        'strike_count': len(strikes),
                        'strikes': list(strikes.keys())[:5],
                        'status': 'SUCCESS'
                    }
                    print(f"✅ Got {len(strikes)} strikes")
                else:
                    results['flate']['status'] = 'NO_DATA'
                    print("⚠️ No data received (Note: Flate Trade option chain may not be fully implemented)")
                    
            except Exception as e:
                results['flate']['status'] = f'ERROR: {e}'
                print(f"❌ Error: {e}")
        else:
            results['flate']['status'] = 'NOT_AVAILABLE'
        
        return results
    
    def print_summary(self, all_results: List[Dict]):
        """Print summary of all tests"""
        print("\n" + "=" * 80)
        print("📋 SUMMARY")
        print("=" * 80)
        
        for result in all_results:
            test_name = result.get('test', 'Unknown')
            print(f"\n{test_name}:")
            
            groww_status = result.get('groww', {}).get('status', 'N/A')
            flate_status = result.get('flate', {}).get('status', 'N/A')
            
            print(f"  Groww:  {groww_status}")
            print(f"  Flate:  {flate_status}")
            
            if 'comparison' in result and result['comparison']:
                match = result['comparison'].get('match', False)
                if match:
                    print(f"  Result: ✅ MATCH")
                else:
                    print(f"  Result: ⚠️ MISMATCH")
        
        print("\n" + "=" * 80)
        print("📊 OVERALL ASSESSMENT")
        print("=" * 80)
        
        # Count matches
        matches = sum(1 for r in all_results 
                     if r.get('comparison', {}).get('match', False))
        total_comparisons = sum(1 for r in all_results 
                               if 'comparison' in r and r['comparison'])
        
        if total_comparisons > 0:
            success_rate = (matches / total_comparisons) * 100
            print(f"\nMatch Rate: {matches}/{total_comparisons} ({success_rate:.1f}%)")
            
            if success_rate >= 80:
                print("✅ GOOD - APIs are producing consistent results")
            elif success_rate >= 50:
                print("⚠️ MODERATE - Some discrepancies found")
            else:
                print("❌ POOR - Significant discrepancies")
        else:
            print("\n⚠️ Not enough data to compare")
        
        print("\nNOTE:")
        print("- Flate Trade option chain may not be fully implemented")
        print("- Small price differences (<0.1%) are normal due to timing")
        print("- For production use, always verify data quality")


def main():
    """Main function"""
    print("=" * 80)
    print("🧪 API COMPARISON TEST - GROWW vs FLATE TRADE")
    print("=" * 80)
    print()
    
    # Initialize comparison
    comparison = APIComparison()
    
    if not comparison.groww and not comparison.flate:
        print("❌ Neither API is available. Cannot run comparison.")
        sys.exit(1)
    
    # Run tests
    all_results = []
    
    # Test 1: Historical candles
    result1 = comparison.compare_historical_candles()
    all_results.append(result1)
    
    # Test 2: LTP
    result2 = comparison.compare_ltp()
    all_results.append(result2)
    
    # Test 3: Option chain
    result3 = comparison.compare_option_chain()
    all_results.append(result3)
    
    # Print summary
    comparison.print_summary(all_results)
    
    print("\n✅ Comparison complete!")


if __name__ == "__main__":
    main()
