# @title V68 - The Master Sniper (Fixed & Integrated)
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
PAPER_MODE = True  # Set to False for Real Money
# -------------------------

# --- ⚙️ CONFIGURATION ---
CAPITAL = 10000.0
LOT_SIZE = 75
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT"  # Master Trend Source
EXPIRY_DATE    = "2025-12-23"             # Option Expiry

# Triggers
VOL_MULTIPLIER = 1.5
OI_DROP_THRESHOLD = -2.0  # Panic Signal (Short Covering)
MAX_SPREAD = 0.50          # Slippage Guard

# Risk Management
SL_POINTS = 4.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0

# Files
LOG_FILE = "V68_BlackBox_Log.csv"
IST = pytz.timezone('Asia/Kolkata')

class MasterSniperV68:
    def __init__(self):
        self.groww = None
        self.position = None
        self.active_symbol = None
        self.entry_price = 0.0
        self.sl_price = 0.0
        self.highest_price = 0.0
        self.trades_today = 0
        self.MAX_TRADES = 3
        self._initialize()

    def _initialize(self):
        try:
            print(f"🔌 Initializing Master Sniper V68 | Mode: {'PAPER' if PAPER_MODE else 'REAL'}")
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            print("✅ Connection Verified.")
            if not os.path.isfile(LOG_FILE):
                with open(LOG_FILE, "w", newline='') as f:
                    csv.writer(f).writerow(["Time", "Fut_LTP", "VWAP", "Vol_Ratio", "Trend", "Strike", "Type", "Opt_LTP", "OI_Chg", "Signal", "PnL"])
        except Exception as e:
            print(f"❌ Auth Failed: {e}"); sys.exit()

    def get_market_data(self):
        """Combined Data Engine: Futures + Option Chain"""
        try:
            # 1. FUTURES TREND (VWAP & VOLUME)
            end = datetime.datetime.now(IST)
            start = datetime.datetime.combine(end.date(), datetime.time(9, 15))
            resp = self.groww.get_historical_candles(
                exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
                start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
                candle_interval="1minute"
            )
            
            if not resp or 'candles' not in resp: return None

            # FIXED: Handles 6 or 7 column responses dynamically
            data = resp['candles']
            cols = ['time','o','h','l','c','v','oi']
            df = pd.DataFrame(data, columns=cols[:len(data[0])])
            
            df['vp'] = ((df['h'] + df['l'] + df['c']) / 3) * df['v']
            vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
            vol_ratio = df['v'].iloc[-1] / df['v'].rolling(20).mean().iloc[-1]
            fut_ltp = df['c'].iloc[-1]

            # 2. DETERMINE TREND & SIDE
            trend = "BULLISH" if fut_ltp > vwap else "BEARISH"
            target_type = "CE" if trend == "BULLISH" else "PE"

            # 3. OPTION DATA (OI & QUOTE)
            atm_strike = int(round(fut_ltp / 50) * 50)
            chain = self.groww.get_option_chain(underlying="NIFTY", expiry_date=EXPIRY_DATE)
            opt_data = chain['strikes'].get(str(atm_strike), {}).get(target_type, {})
            symbol = opt_data.get("trading_symbol")
            
            # Fetch Quote for OI Change % and Spread
            quote = self.groww.get_quote(exchange="NSE", segment="FNO", trading_symbol=symbol)
            
            return {
                "fut_ltp": fut_ltp, "vwap": vwap, "vol_ratio": vol_ratio, "trend": trend,
                "strike": atm_strike, "opt_symbol": symbol, "opt_type": target_type,
                "opt_ltp": quote.get("last_price", opt_data.get("ltp")),
                "oi_chg": quote.get("oi_day_change_percentage", 0),
                "spread": quote.get("offer_price", 0) - quote.get("bid_price", 0)
            }
        except: return None

    def execute(self):
        print("\n🔍 SNIPER ACTIVE: Watching for Short Covering...")
        while True:
            try:
                data = self.get_market_data()
                if not data: 
                    print("\r⚠️ Syncing Data...", end=""); time.sleep(1); continue

                signal = "WAIT"
                pnl = 0.0

                # --- 🔫 ENTRY LOGIC ---
                if self.position is None and self.trades_today < self.MAX_TRADES:
                    # RULE: Trend + Volume + Panic (OI Drop) + Spread Guard
                    if (data['vol_ratio'] > VOL_MULTIPLIER) and \
                       (data['oi_chg'] < OI_DROP_THRESHOLD) and \
                       (data['spread'] < MAX_SPREAD):
                        
                        signal = f"BUY_{data['opt_type']}"
                        self.position = data['opt_type']
                        self.active_symbol = data['opt_symbol']
                        self.entry_price = data['opt_ltp']
                        self.sl_price = self.entry_price - SL_POINTS
                        self.highest_price = self.entry_price
                        self.trades_today += 1
                        print(f"\n🚀 {signal} @ {self.entry_price} | OI Drop: {data['oi_chg']}%")

                # --- 🔄 EXIT/TRAIL LOGIC ---
                elif self.position:
                    # In real mode, you'd re-fetch specifically for active_symbol here
                    curr_p = data['opt_ltp']
                    pnl = (curr_p - self.entry_price) * LOT_SIZE

                    # Trail
                    if curr_p > self.highest_price:
                        self.highest_price = curr_p
                        if (self.highest_price - self.entry_price) > TRAIL_TRIGGER:
                            new_sl = self.highest_price - TRAIL_GAP
                            if new_sl > self.sl_price: self.sl_price = new_sl

                    # Stop Loss
                    if curr_p <= self.sl_price:
                        signal = "EXIT"
                        final_pnl = (self.sl_price - self.entry_price) * LOT_SIZE
                        print(f"\n🔴 EXIT @ {self.sl_price} | PnL: {final_pnl}")
                        self.position = None

                # --- 📝 BLACK BOX LOGGING ---
                ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
                with open(LOG_FILE, "a", newline='') as f:
                    csv.writer(f).writerow([
                        ts, data['fut_ltp'], round(data['vwap'], 2), round(data['vol_ratio'], 2), data['trend'],
                        data['strike'], data['opt_type'], data['opt_ltp'], data['oi_chg'], signal, pnl
                    ])

                # Dashboard
                disp = f"Fut: {data['fut_ltp']} | VWAP: {data['vwap']:.1f} | OI Chg: {data['oi_chg']:.1f}%"
                if self.position: disp += f" | HOLDING {self.active_symbol} | PnL: {pnl:.0f}"
                sys.stdout.write(f"\r[{ts}] {disp}    "); sys.stdout.flush()
                
                time.sleep(1)

            except KeyboardInterrupt: break
            except Exception as e: print(f"\n⚠️ Error: {e}"); time.sleep(2)

if __name__ == "__main__":
    MasterSniperV68().execute()