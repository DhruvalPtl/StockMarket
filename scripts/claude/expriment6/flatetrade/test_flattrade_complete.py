"""
COMPREHENSIVE FLATTRADE DATA TEST
=================================
Tests ALL data types used in the trading bot:
1. NIFTY Spot (Index)
2. NIFTY Futures  
3. Option Chain (Calls & Puts)
4. Individual Option Prices
5. LTP (Last Traded Price)
6. Quotes with Bid/Ask

Saves all data to CSV files for verification.
Run this when market is closed to verify API is working.

Usage:
    python test_flattrade_complete.py
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import time

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig, get_future_symbol, get_option_symbol
from utils.flattrade_wrapper import FlattradeWrapper


class FlattradeDataTester:
    """Comprehensive tester for all Flattrade data types"""
    
    def __init__(self):
        self.api = None
        self.results = {
            'spot': None,
            'future': None,
            'option_chain': None,
            'ce_option': None,
            'pe_option': None
        }
        
    def run_all_tests(self):
        """Run all data fetch tests"""
        print("\n" + "="*70)
        print("🧪 COMPREHENSIVE FLATTRADE DATA TEST")
        print("="*70)
        
        # Step 1: Connect
        if not self.test_connection():
            return False
            
        # Step 2: Test each data type
        self.test_spot_data()
        self.test_future_data()
        self.test_option_chain()
        self.test_individual_options()
        self.test_live_quotes()
        
        # Step 3: Summary
        self.print_summary()
        
        return True
        
    def test_connection(self):
        """Test 1: API Connection"""
        print("\n" + "-"*70)
        print("📡 TEST 1: API CONNECTION")
        print("-"*70)
        
        try:
            self.api = FlattradeWrapper(
                user_id=BotConfig.USER_ID,
                user_token=BotConfig.USER_TOKEN
            )
            
            if not self.api.is_connected:
                print("❌ FAILED: Connection not established")
                print("💡 Run: python gettoken.py")
                return False
                
            print("✅ PASSED: Connected to Flattrade API")
            return True
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
    
    def test_spot_data(self):
        """Test 2: NIFTY Spot Historical Data"""
        print("\n" + "-"*70)
        print("📊 TEST 2: NIFTY SPOT DATA (Last 7 Days)")
        print("-"*70)
        
        try:
            # Fetch last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            print(f"Fetching: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            df = self.fetch_historical_data(
                symbol="NSE-NIFTY",
                exchange="NSE",
                start_date=start_date,
                end_date=end_date,
                interval="5minute"
            )
            
            if df is not None and len(df) > 0:
                csv_file = os.path.join(current_dir, "test_data_spot.csv")
                df.to_csv(csv_file, index=False)
                
                self.results['spot'] = df
                
                print(f"✅ PASSED: {len(df)} candles fetched")
                print(f"📁 Saved: {csv_file}")
                print(f"\n📈 Sample (Last 5 rows):")
                print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail())
            else:
                print("❌ FAILED: No data received")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    def test_future_data(self):
        """Test 3: NIFTY Futures Historical Data"""
        print("\n" + "-"*70)
        print("📊 TEST 3: NIFTY FUTURES DATA (Last 7 Days)")
        print("-"*70)
        
        try:
            fut_symbol = get_future_symbol(BotConfig.FUTURE_EXPIRY)
            print(f"Future Symbol: {fut_symbol}")
            print(f"Expiry: {BotConfig.FUTURE_EXPIRY}")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            df = self.fetch_historical_data(
                symbol=fut_symbol,
                exchange="NSE",
                start_date=start_date,
                end_date=end_date,
                interval="5minute"
            )
            
            if df is not None and len(df) > 0:
                csv_file = os.path.join(current_dir, "test_data_future.csv")
                df.to_csv(csv_file, index=False)
                
                self.results['future'] = df
                
                print(f"✅ PASSED: {len(df)} candles fetched")
                print(f"📁 Saved: {csv_file}")
                print(f"\n📈 Sample (Last 5 rows):")
                print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']].tail())
                
                # Calculate premium
                if self.results['spot'] is not None:
                    spot_last = self.results['spot']['close'].iloc[-1]
                    fut_last = df['close'].iloc[-1]
                    premium = fut_last - spot_last
                    print(f"\n💰 Premium Analysis:")
                    print(f"   Spot LTP: ₹{spot_last:.2f}")
                    print(f"   Future LTP: ₹{fut_last:.2f}")
                    print(f"   Premium: ₹{premium:.2f}")
            else:
                print("❌ FAILED: No data received")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    def test_option_chain(self):
        """Test 4: Option Chain Data"""
        print("\n" + "-"*70)
        print("📊 TEST 4: OPTION CHAIN DATA")
        print("-"*70)
        
        try:
            print(f"Expiry: {BotConfig.OPTION_EXPIRY}")
            
            # Get current NIFTY price to find ATM
            if self.results['spot'] is not None:
                spot_price = self.results['spot']['close'].iloc[-1]
            else:
                spot_price = 24000  # Default
                
            atm_strike = round(spot_price / 50) * 50
            print(f"Current Spot: ₹{spot_price:.2f}")
            print(f"ATM Strike: {atm_strike}")
            
            # Fetch option chain
            chain_data = self.api.get_option_chain(
                exchange="NSE",
                underlying="NIFTY",
                expiry=BotConfig.OPTION_EXPIRY
            )
            
            if chain_data and 'strikes' in chain_data:
                strikes = chain_data['strikes']
                
                # Convert to DataFrame
                rows = []
                for strike, data in strikes.items():
                    row = {'strike': strike}
                    if 'CE' in data:
                        row['ce_ltp'] = data['CE'].get('ltp', 0)
                        row['ce_oi'] = data['CE'].get('oi', 0)
                        row['ce_volume'] = data['CE'].get('volume', 0)
                    if 'PE' in data:
                        row['pe_ltp'] = data['PE'].get('ltp', 0)
                        row['pe_oi'] = data['PE'].get('oi', 0)
                        row['pe_volume'] = data['PE'].get('volume', 0)
                    rows.append(row)
                
                df = pd.DataFrame(rows)
                df = df.sort_values('strike')
                
                csv_file = os.path.join(current_dir, "test_data_option_chain.csv")
                df.to_csv(csv_file, index=False)
                
                self.results['option_chain'] = df
                
                print(f"✅ PASSED: {len(df)} strikes fetched")
                print(f"📁 Saved: {csv_file}")
                print(f"\n📊 Option Chain (Near ATM):")
                
                # Show strikes around ATM
                atm_df = df[(df['strike'] >= atm_strike - 200) & (df['strike'] <= atm_strike + 200)]
                print(atm_df.to_string(index=False))
                
                # Calculate PCR
                total_ce_oi = df['ce_oi'].sum() if 'ce_oi' in df else 0
                total_pe_oi = df['pe_oi'].sum() if 'pe_oi' in df else 0
                pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
                
                print(f"\n📊 PCR (Put-Call Ratio): {pcr:.2f}")
                print(f"   Total CE OI: {total_ce_oi:,}")
                print(f"   Total PE OI: {total_pe_oi:,}")
            else:
                print("❌ FAILED: No option chain data")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    def test_individual_options(self):
        """Test 5: Individual Option Historical Data"""
        print("\n" + "-"*70)
        print("📊 TEST 5: INDIVIDUAL OPTIONS (Last 3 Days)")
        print("-"*70)
        
        try:
            # Get ATM strike
            if self.results['spot'] is not None:
                spot_price = self.results['spot']['close'].iloc[-1]
            else:
                spot_price = 24000
                
            atm_strike = round(spot_price / 50) * 50
            
            # Test CE option
            print(f"\n📞 Testing ATM CALL ({atm_strike}CE):")
            ce_symbol = get_option_symbol(atm_strike, "CE", BotConfig.OPTION_EXPIRY)
            print(f"Symbol: {ce_symbol}")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)
            
            df_ce = self.fetch_historical_data(
                symbol=ce_symbol,
                exchange="NSE",
                start_date=start_date,
                end_date=end_date,
                interval="5minute"
            )
            
            if df_ce is not None and len(df_ce) > 0:
                csv_file = os.path.join(current_dir, "test_data_ce_option.csv")
                df_ce.to_csv(csv_file, index=False)
                self.results['ce_option'] = df_ce
                print(f"✅ PASSED: {len(df_ce)} candles")
                print(f"📁 Saved: {csv_file}")
                print(df_ce[['timestamp', 'open', 'high', 'low', 'close']].tail(3))
            
            # Test PE option
            print(f"\n📉 Testing ATM PUT ({atm_strike}PE):")
            pe_symbol = get_option_symbol(atm_strike, "PE", BotConfig.OPTION_EXPIRY)
            print(f"Symbol: {pe_symbol}")
            
            df_pe = self.fetch_historical_data(
                symbol=pe_symbol,
                exchange="NSE",
                start_date=start_date,
                end_date=end_date,
                interval="5minute"
            )
            
            if df_pe is not None and len(df_pe) > 0:
                csv_file = os.path.join(current_dir, "test_data_pe_option.csv")
                df_pe.to_csv(csv_file, index=False)
                self.results['pe_option'] = df_pe
                print(f"✅ PASSED: {len(df_pe)} candles")
                print(f"📁 Saved: {csv_file}")
                print(df_pe[['timestamp', 'open', 'high', 'low', 'close']].tail(3))
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    def test_live_quotes(self):
        """Test 6: Live Quotes"""
        print("\n" + "-"*70)
        print("📊 TEST 6: LIVE QUOTES")
        print("-"*70)
        
        try:
            quote = self.api.get_quote("NSE-NIFTY")
            if quote and 'last_price' in quote:
                print(f"✅ PASSED: Live quote received")
                print(f"   NIFTY LTP: ₹{quote['last_price']:.2f}")
            else:
                print("❌ FAILED: No quote data")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
    
    def fetch_historical_data(self, symbol, exchange, start_date, end_date, interval):
        """Helper to fetch historical data"""
        all_candles = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            day_start = current_date.replace(hour=9, minute=15, second=0, microsecond=0)
            day_end = current_date.replace(hour=15, minute=30, second=0, microsecond=0)
            
            try:
                resp = self.api.get_historical_candles(
                    exchange=exchange,
                    segment="CASH" if "FUT" not in symbol and symbol.count('-') < 4 else "FNO",
                    symbol=symbol,
                    start_time=day_start.strftime("%Y-%m-%d %H:%M:%S"),
                    end_time=day_end.strftime("%Y-%m-%d %H:%M:%S"),
                    interval=interval
                )
                
                if resp and 'candles' in resp and len(resp['candles']) > 0:
                    all_candles.extend(resp['candles'])
                    print(f"   ✓ {current_date.strftime('%Y-%m-%d')}: {len(resp['candles'])} candles")
                    
            except Exception as e:
                print(f"   ✗ {current_date.strftime('%Y-%m-%d')}: {e}")
            
            current_date += timedelta(days=1)
            time.sleep(0.5)  # Rate limiting
        
        if len(all_candles) == 0:
            return None
        
        df = pd.DataFrame(all_candles)
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'][:len(df.columns)]
        df = df.sort_values('timestamp')
        
        return df
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        tests_passed = 0
        tests_total = 6
        
        if self.api and self.api.is_connected:
            print("✅ API Connection: PASSED")
            tests_passed += 1
        else:
            print("❌ API Connection: FAILED")
            
        if self.results['spot'] is not None and len(self.results['spot']) > 0:
            print(f"✅ Spot Data: PASSED ({len(self.results['spot'])} candles)")
            tests_passed += 1
        else:
            print("❌ Spot Data: FAILED")
            
        if self.results['future'] is not None and len(self.results['future']) > 0:
            print(f"✅ Future Data: PASSED ({len(self.results['future'])} candles)")
            tests_passed += 1
        else:
            print("❌ Future Data: FAILED")
            
        if self.results['option_chain'] is not None and len(self.results['option_chain']) > 0:
            print(f"✅ Option Chain: PASSED ({len(self.results['option_chain'])} strikes)")
            tests_passed += 1
        else:
            print("❌ Option Chain: FAILED")
            
        if self.results['ce_option'] is not None:
            print(f"✅ CE Option: PASSED ({len(self.results['ce_option'])} candles)")
            tests_passed += 1
        else:
            print("❌ CE Option: FAILED")
            
        if self.results['pe_option'] is not None:
            print(f"✅ PE Option: PASSED ({len(self.results['pe_option'])} candles)")
            tests_passed += 1
        else:
            print("❌ PE Option: FAILED")
        
        print("="*70)
        print(f"TOTAL: {tests_passed}/{tests_total} tests passed")
        print("="*70)
        
        print("\n📁 CSV Files Created:")
        csv_files = [
            "test_data_spot.csv",
            "test_data_future.csv",
            "test_data_option_chain.csv",
            "test_data_ce_option.csv",
            "test_data_pe_option.csv"
        ]
        for f in csv_files:
            path = os.path.join(current_dir, f)
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024
                print(f"   ✓ {f} ({size:.1f} KB)")
        
        print("\n" + "="*70)


if __name__ == "__main__":
    tester = FlattradeDataTester()
    tester.run_all_tests()
