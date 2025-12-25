"""
API-BASED BACKTESTER
Fetch historical data directly from Groww API and backtest
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from growwapi import GrowwAPI
import time

class APIBacktester:
    def __init__(self, api_key, api_secret, start_date, end_date, expiry_date, initial_capital=10000):
        print("\n" + "="*70)
        print("🔌 API-BASED BACKTESTER")
        print("="*70)
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.start_date = start_date
        self.end_date = end_date
        self.expiry_date = expiry_date
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.lot_size = 75
        
        # Connect
        self._connect()
        
        # Trading tracking
        self.trades = []
        self.active_position = None
        self.daily_pnl = 0
        self.max_loss_limit = initial_capital * 0.10
        
        # Data storage
        self.historical_data = []
        self.total_ticks_processed = 0
        
        print(f"💰 Initial Capital: Rs.{initial_capital:,.2f}")
        print(f"🛡️  Max Daily Loss: Rs.{self.max_loss_limit:,.2f}")
        print(f"📅 Period: {start_date} to {end_date}")
        print("="*70 + "\n")
    
    def _connect(self):
        """Connect to Groww API"""
        try:
            token = GrowwAPI.get_access_token(api_key=self.api_key, secret=self.api_secret)
            self.groww = GrowwAPI(token)
            print("✅ Connected to Groww API")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            exit(1)
    
    def fetch_historical_data(self, interval="5minute"):
        """Fetch historical data from Groww API"""
        print(f"📡 Fetching historical data ({interval} interval)...")
        
        try:
            # Fetch Spot data
            print("  - Fetching Spot data...")
            spot_data = self.groww.get_historical_candles(
                "NSE", "CASH", "NSE-NIFTY",
                self.start_date, self.end_date, interval
            )
            
            if not spot_data or 'candles' not in spot_data:
                print("❌ No spot data received")
                return False
            
            df_spot = pd.DataFrame(spot_data['candles'], columns=['timestamp','open','high','low','close','volume','oi'])
            df_spot['timestamp'] = pd.to_datetime(df_spot['timestamp'], unit='s')
            
            print(f"  ✅ Fetched {len(df_spot)} spot candles")
            
            # Calculate indicators
            print("  - Calculating indicators...")
            df_spot['rsi'] = self._calculate_rsi(df_spot['close'])
            df_spot['ema5'] = df_spot['close'].ewm(span=5, adjust=False).mean()
            df_spot['ema13'] = df_spot['close'].ewm(span=13, adjust=False).mean()
            df_spot['vwap'] = (df_spot['close'] * df_spot['volume']).cumsum() / df_spot['volume'].cumsum()
            
            # Fetch Option Chain for each candle (sample every 5th candle to save API calls)
            print("  - Fetching option chain data (sampled)...")
            chain_data = []
            
            for idx in range(0, len(df_spot), 5):  # Every 5th candle
                row = df_spot.iloc[idx]
                time.sleep(1)  # Rate limiting
                
                try:
                    atm_strike = round(row['close'] / 50) * 50
                    chain = self.groww.get_option_chain("NSE", "NIFTY", self.expiry_date)
                    
                    if chain and 'strikes' in chain:
                        # Extract ATM data
                        ce_data = chain['strikes'].get(str(atm_strike), {}).get('CE', {})
                        pe_data = chain['strikes'].get(str(atm_strike), {}).get('PE', {})
                        
                        # Calculate PCR
                        total_ce_oi = sum(s.get('CE', {}).get('open_interest', 0) for s in chain['strikes'].values())
                        total_pe_oi = sum(s.get('PE', {}).get('open_interest', 0) for s in chain['strikes'].values())
                        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
                        
                        chain_data.append({
                            'timestamp': row['timestamp'],
                            'atm_strike': atm_strike,
                            'ce_price': ce_data.get('ltp', 0),
                            'pe_price': pe_data.get('ltp', 0),
                            'ce_oi': ce_data.get('open_interest', 0),
                            'pe_oi': pe_data.get('open_interest', 0),
                            'pcr': pcr
                        })
                    
                    if (idx // 5) % 10 == 0:
                        print(f"    Progress: {idx}/{len(df_spot)} candles")
                
                except Exception as e:
                    print(f"    ⚠️ Chain error at {idx}: {e}")
                    continue
            
            df_chain = pd.DataFrame(chain_data)
            
            # Merge spot and chain data
            self.historical_data = pd.merge_asof(
                df_spot.sort_values('timestamp'),
                df_chain.sort_values('timestamp'),
                on='timestamp',
                direction='nearest'
            )
            
            # Fill NaN values
            self.historical_data = self.historical_data.fillna(method='ffill').fillna(0)
            
            print(f"  ✅ Processed {len(self.historical_data)} complete datapoints")
            print("="*70 + "\n")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False
    
    def _calculate_rsi(self, series, period=14):
        """Calculate RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def run(self, strategy_func):
        """Run backtest with custom strategy"""
        if len(self.historical_data) == 0:
            print("❌ No historical data available. Fetch data first.")
            return
        
        print("🚀 Starting Backtest...\n")
        
        for idx, row in self.historical_data.iterrows():
            self.total_ticks_processed += 1
            
            # Check risk limits
            if abs(self.daily_pnl) >= self.max_loss_limit:
                print(f"\n🛑 Daily loss limit hit at tick {idx}")
                break
            
            # Build engine state
            engine_state = {
                'timestamp': row['timestamp'],
                'spot': row['close'],
                'rsi': row['rsi'],
                'vwap': row['vwap'],
                'ema5': row['ema5'],
                'ema13': row['ema13'],
                'pcr': row.get('pcr', 0),
                'atm_strike': row.get('atm_strike', 0),
                'ce_price': row.get('ce_price', 0),
                'pe_price': row.get('pe_price', 0),
                'ce_oi': row.get('ce_oi', 0),
                'pe_oi': row.get('pe_oi', 0)
            }
            
            # If no position, check for entry
            if not self.active_position:
                signal = strategy_func(row, engine_state)
                
                if signal in ['BUY_CE', 'BUY_PE']:
                    self._enter_position(row, signal, engine_state)
            
            # If position active, manage it
            else:
                self._manage_position(row, engine_state)
            
            # Print progress
            if self.total_ticks_processed % 50 == 0:
                self._print_progress(row)
        
        # Close any open position
        if self.active_position:
            last_row = self.historical_data.iloc[-1]
            engine_state = {
                'timestamp': last_row['timestamp'],
                'spot': last_row['close'],
                'ce_price': last_row.get('ce_price', 0),
                'pe_price': last_row.get('pe_price', 0)
            }
            self._exit_position(last_row, engine_state, "END_OF_DATA")
        
        # Print results
        self._print_results()
    
    def _enter_position(self, row, signal, engine_state):
        """Enter a position"""
        if signal == 'BUY_CE':
            entry_price = engine_state['ce_price']
            option_type = 'CE'
        else:
            entry_price = engine_state['pe_price']
            option_type = 'PE'
        
        if entry_price == 0:
            return
        
        total_cost = entry_price * self.lot_size
        if total_cost > self.capital * 0.7:
            return
        
        self.active_position = {
            'type': option_type,
            'entry_price': entry_price,
            'entry_time': engine_state['timestamp'],
            'entry_tick': self.total_ticks_processed,
            'peak': entry_price,
            'target': entry_price + 10,
            'stop_loss': entry_price - 5
        }
        
        print(f"🟢 ENTRY: {option_type} @ Rs.{entry_price:.2f} | {engine_state['timestamp']}")
    
    def _manage_position(self, row, engine_state):
        """Manage active position"""
        current_price = engine_state['ce_price'] if self.active_position['type'] == 'CE' else engine_state['pe_price']
        
        if current_price == 0:
            return
        
        if current_price > self.active_position['peak']:
            self.active_position['peak'] = current_price
        
        exit_reason = None
        
        if current_price >= self.active_position['target']:
            exit_reason = "TARGET"
        elif current_price <= self.active_position['stop_loss']:
            exit_reason = "STOP_LOSS"
        elif self.active_position['peak'] > self.active_position['target']:
            if current_price <= self.active_position['peak'] * 0.9:
                exit_reason = "TRAILING_STOP"
        
        ticks_held = self.total_ticks_processed - self.active_position['entry_tick']
        if ticks_held > 360:  # 30 minutes (5min candles)
            exit_reason = "TIME_EXIT"
        
        if exit_reason:
            self._exit_position(row, engine_state, exit_reason)
    
    def _exit_position(self, row, engine_state, reason):
        """Exit position"""
        exit_price = engine_state['ce_price'] if self.active_position['type'] == 'CE' else engine_state['pe_price']
        
        if exit_price == 0:
            return
        
        pnl = (exit_price - self.active_position['entry_price']) * self.lot_size
        self.capital += pnl
        self.daily_pnl += pnl
        
        self.trades.append({
            'entry_time': self.active_position['entry_time'],
            'exit_time': engine_state['timestamp'],
            'type': self.active_position['type'],
            'entry_price': self.active_position['entry_price'],
            'exit_price': exit_price,
            'peak': self.active_position['peak'],
            'pnl': pnl,
            'exit_reason': reason
        })
        
        print(f"🔴 EXIT: {reason} @ Rs.{exit_price:.2f} | PnL: Rs.{pnl:,.2f}")
        
        self.active_position = None
    
    def _print_progress(self, row):
        """Print progress"""
        status = "In Position" if self.active_position else "Scanning"
        print(f"⏳ {row['timestamp']} | {status} | Balance: Rs.{self.capital:,.2f}")
    
    def _print_results(self):
        """Print backtest results"""
        print("\n" + "="*70)
        print("📊 BACKTEST RESULTS")
        print("="*70)
        
        total_pnl = self.capital - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        print(f"Initial Capital: Rs.{self.initial_capital:,.2f}")
        print(f"Final Capital:   Rs.{self.capital:,.2f}")
        print(f"Total PnL:       Rs.{total_pnl:,.2f} ({total_return_pct:.2f}%)")
        print(f"")
        
        if len(self.trades) == 0:
            print("No trades executed.")
            print("="*70 + "\n")
            return
        
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        print(f"Total Trades:    {len(self.trades)}")
        print(f"Winning Trades:  {len(winning_trades)}")
        print(f"Losing Trades:   {len(losing_trades)}")
        print(f"Win Rate:        {len(winning_trades)/len(self.trades)*100:.1f}%")
        print("="*70 + "\n")
        
        # Save results
        df = pd.DataFrame(self.trades)
        filename = f"API_Backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"📝 Results saved to: {filename}")


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Configuration
    API_KEY = "YOUR_API_KEY"
    API_SECRET = "YOUR_API_SECRET"
    START_DATE = "2025-12-24 09:15:00"
    END_DATE = "2025-12-24 15:30:00"
    EXPIRY_DATE = "2025-12-30"
    INITIAL_CAPITAL = 10000
    
    # Create backtester
    backtester = APIBacktester(
        API_KEY, API_SECRET,
        START_DATE, END_DATE, EXPIRY_DATE,
        INITIAL_CAPITAL
    )
    
    # Fetch historical data
    if backtester.fetch_historical_data(interval="5minute"):
        # Run backtest with your strategy
        from claude_csv_backtester import momentum_burst_strategy
        backtester.run(momentum_burst_strategy)
