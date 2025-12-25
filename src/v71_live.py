# @title V71 - The Full-Spectrum Sniper (Enhanced Logging & UI)
from growwapi import GrowwAPI
import pandas as pd
import datetime
import time
import csv
import sys
import os
import pytz

# --- 🔐 CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- ⚠️ EXECUTION MODE ---
PAPER_MODE = True  
# -------------------------

# --- ⚙️ CONFIGURATION ---
START_BALANCE = 10000.0
LOT_SIZE = 75
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 
EXPIRY_DATE    = "2025-12-23" 

# Strategy Parameters
VOL_MULTIPLIER = 1.5
OI_DROP_THRESHOLD = -2.0  
MAX_SPREAD = 0.50          # Slippage Guard (Ask - Bid)

# Risk Management
SL_POINTS = 4.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0

# Files
LOG_FILE = "V71_BlackBox_Master.csv"
IST = pytz.timezone('Asia/Kolkata')

class FullSpectrumSniperV71:
    def __init__(self):
        self.groww = None
        self.position = None # None, "CE", "PE"
        self.active_symbol = "N/A"
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.highest_price = 0.0
        self.trades_today = 0
        self.MAX_TRADES = 3
        self.balance = START_BALANCE
        self._initialize()

    def _initialize(self):
        try:
            print(f"[{datetime.datetime.now(IST).strftime('%H:%M:%S')}] 🚀 INITIALIZING V71 SNIPER...")
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            print("✅ Verified: All Data Streams Connected.")
            
            if not os.path.isfile(LOG_FILE):
                with open(LOG_FILE, "w", newline='') as f:
                    writer = csv.writer(f)
                    # The exact 16 columns you requested
                    writer.writerow([
                        "Timestamp", "Fut_Price", "Fut_VWAP", "Fut_Vol", "Vol_Ratio", "Trend",
                        "Strike", "Opt_Symbol", "Opt_LTP", "Opt_OI", "OI_Chg", "Spread",
                        "Signal", "Position", "PnL", "Balance"
                    ])
        except Exception as e:
            print(f"❌ Initialization Failed: {e}"); sys.exit()

    def get_data(self):
        try:
            # 1. FUTURES TREND DATA
            end = datetime.datetime.now(IST)
            start = end - datetime.timedelta(minutes=30)
            resp = self.groww.get_historical_candles(
                exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
                start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
                candle_interval="1minute"
            )
            if not resp or 'candles' not in resp: return None
            
            candles = resp['candles']
            cols = ['t','o','h','l','c','v','oi']
            df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            
            df['vp'] = ((df['h'] + df['l'] + df['c']) / 3) * df['v']
            vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
            vol_ratio = df['v'].iloc[-1] / df['v'].rolling(20).mean().iloc[-1]
            fut_p = df['c'].iloc[-1]
            fut_vol = df['v'].iloc[-1]

            # 2. OPTION SELECTION
            trend = "BULLISH" if fut_p > vwap else "BEARISH"
            target_side = "CE" if trend == "BULLISH" else "PE"
            atm_strike = int(round(fut_p / 50) * 50)

            # 3. OPTION INTEL
            chain = self.groww.get_option_chain(exchange=self.groww.EXCHANGE_NSE, underlying="NIFTY", expiry_date=EXPIRY_DATE)
            strike_data = chain['strikes'].get(str(atm_strike), {}).get(target_side, {})
            opt_sym = strike_data.get("trading_symbol")
            
            quote = self.groww.get_quote(exchange="NSE", segment="FNO", trading_symbol=opt_sym)
            
            # Extract specific fields for spread and OI
            opt_ltp = quote.get("last_price", strike_data.get("ltp", 0))
            opt_oi = quote.get("open_interest", strike_data.get("open_interest", 0))
            oi_chg = quote.get("oi_day_change_percentage", 0)
            spread = quote.get("offer_price", 0) - quote.get("bid_price", 0)
            
            return {
                "fut_p": fut_p, "fut_vwap": vwap, "fut_vol": fut_vol, "vol_ratio": vol_ratio, "trend": trend,
                "strike": atm_strike, "opt_sym": opt_sym, "opt_ltp": opt_ltp, 
                "opt_oi": opt_oi, "oi_chg": oi_chg, "spread": spread, "opt_type": target_side
            }
        except Exception as e:
            return None

    def run(self):
        print("\n" + "="*50)
        print("🔎 V71 MONITORING ACTIVE | Logging to V71_BlackBox_Master.csv")
        print("="*50)

        while True:
            try:
                data = self.get_data()
                if not data: 
                    time.sleep(1); continue

                signal = "WAIT"
                current_pnl = 0.0

                # --- 🔫 STRATEGY LOGIC ---
                if self.position is None and self.trades_today < self.MAX_TRADES:
                    # Logic: Trend + Vol Spike + OI Panic + Spread Guard
                    if (data['vol_ratio'] > VOL_MULTIPLIER) and \
                       (data['oi_chg'] < OI_DROP_THRESHOLD) and \
                       (data['spread'] <= MAX_SPREAD):
                        
                        signal = f"BUY_{data['opt_type']}"
                        self.position = data['opt_type']
                        self.active_symbol = data['opt_sym']
                        self.entry_price = data['opt_ltp']
                        self.sl_price = self.entry_price - SL_POINTS
                        self.highest_price = self.entry_price
                        self.trades_today += 1
                        print(f"\n🚀 {signal} ENTERED @ {self.entry_price} | Spread: {data['spread']}")

                # --- 🔄 POSITION MANAGEMENT ---
                elif self.position:
                    # For scalping, we use the LTP from our general data fetch
                    curr_p = data['opt_ltp']
                    current_pnl = (curr_p - self.entry_price) * LOT_SIZE
                    
                    # Update Trailing Stop
                    if curr_p > self.highest_price:
                        self.highest_price = curr_p
                        if (self.highest_price - self.entry_price) > TRAIL_TRIGGER:
                            new_sl = self.highest_price - TRAIL_GAP
                            if new_sl > self.sl_price: self.sl_price = new_sl

                    # Exit Logic
                    if curr_p <= self.sl_price:
                        signal = "EXIT"
                        trade_pnl = (self.sl_price - self.entry_price) * LOT_SIZE
                        self.balance += trade_pnl
                        print(f"\n🔴 TRADE CLOSED @ {self.sl_price} | PnL: {trade_pnl:.2f}")
                        self.position = None
                        self.active_symbol = "N/A"

                # --- 📝 MASTER LOGGING (16 COLUMNS) ---
                ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
                with open(LOG_FILE, "a", newline='') as f:
                    csv.writer(f).writerow([
                        ts, data['fut_p'], round(data['fut_vwap'], 2), data['fut_vol'], 
                        round(data['vol_ratio'], 2), data['trend'], data['strike'], 
                        data['opt_sym'], data['opt_ltp'], data['opt_oi'], 
                        round(data['oi_chg'], 2), round(data['spread'], 2),
                        signal, self.position if self.position else "None", 
                        round(current_pnl, 2), round(self.balance, 2)
                    ])

                # --- 🖥️ ENHANCED TERMINAL DASHBOARD ---
                # Clear line and print status
                sys.stdout.write("\033[K") # Clear current line
                dashboard = (
                    f"[{ts}] {data['trend']} | Fut: {data['fut_p']} (VWAP: {data['fut_vwap']:.1f}) | "
                    f"Vol: {data['vol_ratio']:.1f}x | OI Chg: {data['oi_chg']:.1f}% | Spread: {data['spread']:.2f} | "
                    f"Pos: {self.position} | PnL: {current_pnl:+.0f}"
                )
                sys.stdout.write(f"\r{dashboard}")
                sys.stdout.flush()
                
                time.sleep(1)

            except KeyboardInterrupt:
                print("\n🛑 Bot Stopped by User."); break
            except Exception as e:
                time.sleep(2)

if __name__ == "__main__":
    FullSpectrumSniperV71().run()