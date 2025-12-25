# @title V82 - The Glass Box Sniper (Verbose Debugging)
import logging
import csv
import os
import sys
import time
import datetime
import pandas as pd
import pytz
from collections import deque, defaultdict
from growwapi import GrowwAPI

# ==========================================
# 🔐 USER CONFIGURATION
# ==========================================
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MzcwMzEsImlhdCI6MTc2NjEzNzAzMSwibmJmIjoxNzY2MTM3MDMxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkYjY5YTI4MS04YzVkLTRhZDMtYTYwMy1iMWRkZjlmMjBkZGZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjJmZmJiNTM1LWRkODQtNDVhZS1hMjkwLWUyZWFmMGQ3NGZlMFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTYyLjE1OC41MS4xNzUsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTQ1MzcwMzEzODJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.C_j_AbvZPNY1wb7hjEMGGO9CP0xhen40jwWMRLPKh73dd6T8sQKn32HmTkpAQtUzdEm2YCxPaJdy3aW_ojvo7A"
API_SECRET = "cE#YaAvu27#kS)axpmB1p#4kKlvv7%ef"

FUT_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 
EXPIRY     = "2025-12-23" 
VOL_MULT   = 1.5
OI_DROP    = -1.0 
IST = pytz.timezone('Asia/Kolkata')

# Trading Params
START_BAL  = 10000.0
LOT_SIZE   = 75
SL_POINTS  = 4.0
TRAIL_TRIG = 3.0
TRAIL_GAP  = 2.0
MAX_SPREAD = 0.50
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("V82")

DATA_FILE = "V82_Live_Log.csv"
TRADE_FILE = "V82_Trade_Journal.csv"

class GlassBoxSniperV82:
    def __init__(self):
        self.connect_api()
        self.pos = None
        self.active_sym = None
        self.entry_p = 0.0
        self.sl_p = 0.0
        self.high_p = 0.0
        self.bal = START_BAL
        self.trades = 0
        self.oi_memory = defaultdict(lambda: deque(maxlen=300))
        self._init_files()

    def connect_api(self):
        try:
            logger.info("🔌 Connecting to Groww...")
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            logger.info("✅ Connection Verified.")
        except Exception as e:
            logger.error(f"❌ Auth Failed: {e}")
            print("Check your API Key/Secret.")
            sys.exit()

    def _init_files(self):
        if not os.path.isfile(DATA_FILE):
            with open(DATA_FILE, "w", newline='') as f:
                csv.writer(f).writerow([
                    "Time", "Spot_Price", "Fut_Price", "VWAP", "Vol_Ratio", "Trend",
                    "Strike", "Symbol", "LTP", "OI_Panic%", "Spread", "Signal", "PnL", "Balance"
                ])
        if not os.path.isfile(TRADE_FILE):
            with open(TRADE_FILE, "w", newline='') as f:
                csv.writer(f).writerow(["Time", "Action", "Symbol", "Price", "PnL", "Reason"])

    def log_trade(self, action, price, pnl, reason):
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        with open(TRADE_FILE, "a", newline='') as f:
            csv.writer(f).writerow([ts, action, self.active_sym, price, pnl, reason])
            f.flush()

    def get_symbol_panic(self, symbol, current_oi):
        now = time.time()
        self.oi_memory[symbol].append((now, current_oi))
        old_oi = current_oi
        for ts, oi in self.oi_memory[symbol]:
            if now - ts >= 180: break
            old_oi = oi # Keep going back until ~3 mins
        if old_oi == 0: return 0.0
        return ((current_oi - old_oi) / old_oi) * 100

    def get_spot_price(self):
        """Robust Spot Price Fetcher with Fallbacks"""
        try:
            # Method 1: NSE_NIFTY (Your preferred method)
            # Note: passing list ["NSE_NIFTY"] as some API versions require list
            ltp = self.groww.get_ltp(segment="CASH", exchange_trading_symbols=["NSE_NIFTY"])
            if ltp and 'NSE_NIFTY' in ltp: return ltp['NSE_NIFTY']
            
            # Method 2: Nifty 50 String
            ltp = self.groww.get_ltp(segment="CASH", exchange_trading_symbols=["Nifty 50"])
            if ltp and 'Nifty 50' in ltp: return ltp['Nifty 50']
            
            # Method 3: Try getting Index OHLC
            resp = self.groww.get_index_latest_ohlc("NSE", "NIFTY 50")
            if resp and 'close' in resp: return resp['close']

        except Exception as e:
            logger.warning(f"⚠️ Spot Price Warning: {e}")
        
        return 0.0 # Failed

    def get_market_data(self):
        # 1. FUTURES (Essential)
        try:
            end = datetime.datetime.now(IST)
            start = end - datetime.timedelta(minutes=30)
            resp = self.groww.get_historical_candles(
                "NSE", "FNO", FUT_SYMBOL, 
                start.strftime("%Y-%m-%d %H:%M:%S"), 
                end.strftime("%Y-%m-%d %H:%M:%S"), "1minute"
            )
            if not resp or 'candles' not in resp: 
                print("❌ Error: No Futures Data returned")
                return None
            
            candles = resp['candles']
            df = pd.DataFrame(candles, columns=['t','o','h','l','c','v','oi'][:len(candles[0])])
            
            df['vp'] = ((df['h']+df['l']+df['c'])/3)*df['v']
            vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
            fut_p = df['c'].iloc[-1]
            vol = df['v'].iloc[-1]
            avg_vol = df['v'].rolling(20).mean().iloc[-1]
            if pd.isna(avg_vol): avg_vol = vol
            
        except Exception as e:
            print(f"❌ Error fetching Futures: {e}")
            return None

        # 2. SPOT PRICE (Robust)
        spot_p = self.get_spot_price()
        if spot_p == 0: 
            spot_p = fut_p # Emergency Fallback
            # print("⚠️ Using Futures as Spot Proxy")

        # 3. SELECT STRIKE
        try:
            trend = "BULLISH" if fut_p > vwap else "BEARISH"
            if self.pos:
                sym = self.active_sym
                strike = "LOCKED"
            else:
                target = "CE" if trend == "BULLISH" else "PE"
                strike = int(round(spot_p / 50) * 50)
                chain = self.groww.get_option_chain("NSE", "NIFTY", EXPIRY)
                if str(strike) not in chain['strikes']: 
                    print(f"❌ Strike {strike} not found in chain")
                    return None
                sym = chain['strikes'][str(strike)][target]['trading_symbol']
        except Exception as e:
            print(f"❌ Error Selecting Strike: {e}")
            return None

        # 4. GET OPTION DATA
        try:
            quote = self.groww.get_quote("NSE", "CASH", sym)
            if not quote: 
                print(f"❌ No Quote for {sym}")
                return None
            
            ltp = quote.get('last_price', 0)
            oi = quote.get('open_interest', 0)
            panic = self.get_symbol_panic(sym, oi)
            spread = (quote.get('offer_price', 0) or 0) - (quote.get('bid_price', 0) or 0)
            
            return {
                "spot_p": spot_p, "fut_p": fut_p, "vwap": vwap, 
                "vol": vol, "avg_vol": avg_vol, "trend": trend,
                "strike": strike, "sym": sym, "ltp": ltp,
                "panic": panic, "spr": spread, "type": "CE" if "CE" in sym else "PE"
            }
        except Exception as e:
            print(f"❌ Error fetching Quote: {e}")
            return None

    def run(self):
        logger.info("🚀 V82 Glass Box Active.")
        while True:
            try:
                d = self.get_market_data()
                if not d: 
                    time.sleep(1); continue

                sig = "WAIT"
                current_pnl = 0.0
                vol_ratio = d['vol'] / d['avg_vol'] if d['avg_vol'] > 0 else 0

                # ENTRY
                if self.pos is None and self.trades < 5:
                    if (vol_ratio > VOL_MULT) and (d['panic'] < OI_DROP) and (d['spr'] < MAX_SPREAD):
                        sig = f"BUY_{d['type']}"
                        self.pos = d['type']
                        self.active_sym = d['sym']
                        self.entry_p = d['ltp']
                        self.sl_p, self.high_p = self.entry_p - SL_POINTS, self.entry_p
                        self.trades += 1
                        logger.info(f"🔥 ENTRY: {sig} {d['sym']} @ {self.entry_p} | Panic: {d['panic']:.2f}%")
                        self.log_trade("BUY", self.entry_p, 0.0, "Panic_Entry")

                # EXIT
                elif self.pos:
                    current_pnl = (d['ltp'] - self.entry_p) * LOT_SIZE
                    if d['ltp'] > self.high_p:
                        self.high_p = d['ltp']
                        if (self.high_p - self.entry_p) > TRAIL_TRIG:
                            self.sl_p = max(self.sl_p, self.high_p - TRAIL_GAP)
                    if d['ltp'] <= self.sl_p:
                        sig = "EXIT"
                        final_pnl = (self.sl_p - self.entry_p) * LOT_SIZE
                        self.bal += final_pnl
                        logger.info(f"🔴 EXIT: {self.active_sym} @ {self.sl_p} | PnL: {final_pnl}")
                        self.log_trade("SELL", self.sl_p, final_pnl, "Stop_Hit")
                        self.pos = None
                        self.active_sym = None

                # LOGGING
                ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
                with open(DATA_FILE, "a", newline='') as f:
                    csv.writer(f).writerow([
                        ts, d['spot_p'], d['fut_p'], round(d['vwap'], 2), round(vol_ratio, 2),
                        d['trend'], d['strike'], d['sym'], d['ltp'], 
                        round(d['panic'], 2), round(d['spr'], 2),
                        sig, round(current_pnl, 2), round(self.bal, 2)
                    ])
                    f.flush()

                # DASHBOARD
                sys.stdout.write(f"\r[{ts}] {d['trend']} | Spot: {d['spot_p']} | Panic: {d['panic']:.2f}% | Vol: {vol_ratio:.1f}x   ")
                sys.stdout.flush()
                time.sleep(1)

            except KeyboardInterrupt:
                print("\n🛑 Stopped."); break
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    GlassBoxSniperV82().run()