# @title V78 - Hybrid Sniper (Spot ATM + Futures Vol + Reversal Scalp)
import logging
import csv
import os
import sys
import time
import datetime
import pandas as pd
import pandas_ta as ta
import numpy as np
import pytz
from collections import deque, defaultdict
from growwapi import GrowwAPI

# --- CREDENTIALS ---
API_KEY = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ1MTk4NDYsImlhdCI6MTc2NjExOTg0NiwibmJmIjoxNzY2MTE5ODQ2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJkMDBlZDRiNi0yZGUyLTQyOGYtYmQ3Ny01NWM1NDI1OTE1MzlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcImIyNWExYmZkLTI0YmUtNGRiMi04ZWVlLTNjZjE3NTllNzE3YVwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmQwYjg6ZWQ2ZTozOTc0OmJmMTUsMTcyLjY5LjE3OC42MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDUxOTg0NjYzOX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.pSwqU03XqcvDO17Fui2bwFfGTt6o183FURSuUZMIgKMxqXSRx_PNphPRBd3fwnr0JdUBNS1lhQUPv7yjllZqgg"
API_SECRET = "5JP85BqePVDPjyKY)9Z-YLJ@*a%zJ&9)"

# --- CONFIGURATION ---
START_BALANCE = 10000.0
LOT_SIZE = 75
FUTURES_SYMBOL = "NSE-NIFTY-30Dec25-FUT" 
EXPIRY_DATE    = "2025-12-23" 
IST = pytz.timezone('Asia/Kolkata')

# Strategy Parameters
VOL_MULTIPLIER = 1.5
OI_DROP_THRESHOLD = -1.0  
MAX_SPREAD = 0.50          
SL_POINTS = 4.0
TRAIL_TRIGGER = 3.0
TRAIL_GAP = 2.0

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("sniper_system.log", encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("V78")

# Files
DATA_FILE = "V78_Hybrid_Log.csv"
TRADE_FILE = "V78_Trade_Journal.csv"

class HybridSniperV78:
    def __init__(self):
        self.groww = None
        self.pos = None        
        self.active_sym = None 
        self.entry_p = 0.0
        self.sl_p = 0.0
        self.high_p = 0.0
        self.bal = START_BALANCE
        self.trades = 0
        
        # History for Panic Calculation
        self.oi_memory = defaultdict(lambda: deque(maxlen=300))
        
        self._init_api()
        self._init_files()

    def _init_api(self):
        try:
            logger.info("Connecting to Groww...")
            token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
            self.groww = GrowwAPI(token)
            logger.info("API Connection Verified.")
        except Exception as e:
            logger.error(f"Connection Failed: {e}")
            sys.exit()

    def _init_files(self):
        if not os.path.isfile(DATA_FILE):
            with open(DATA_FILE, "w", newline='') as f:
                csv.writer(f).writerow([
                    "Timestamp", "Spot_Price", "Fut_Price", "VWAP", "Vol_Ratio", "Trend",
                    "Strike", "Opt_Symbol", "Opt_LTP", "Panic%", "Spread", "Signal", "PnL", "Balance"
                ])
        
        if not os.path.isfile(TRADE_FILE):
            with open(TRADE_FILE, "w", newline='') as f:
                csv.writer(f).writerow(["Time", "Action", "Symbol", "Price", "PnL", "Reason"])

    def log_trade(self, action, price, pnl, reason):
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        with open(TRADE_FILE, "a", newline='') as f:
            csv.writer(f).writerow([ts, action, self.active_sym, price, pnl, reason])
            f.flush()

    def get_symbol_specific_panic(self, symbol, current_oi):
        now = time.time()
        self.oi_memory[symbol].append((now, current_oi))
        history = self.oi_memory[symbol]
        
        old_oi = current_oi
        for ts, oi in history:
            if now - ts >= 180: # 3 mins ago
                old_oi = oi
                break
        
        if old_oi == 0: return 0.0
        return ((current_oi - old_oi) / old_oi) * 100

    def get_nifty_spot(self):
        """Fetches Nifty 50 Spot Price for correct ATM Strike"""
        try:
            # Try fetching Index Spot. If this fails, user might need to adjust the symbol key
            # Common keys: "Nifty 50", "NSE Index", or checking recent cash market LTP
            resp = self.groww.get_index_latest_ohlc("NSE", "NIFTY")
            if resp and 'close' in resp:
                return resp['close']
            
            # Fallback: Get LTP of a proxy if index fails
            ltp = self.groww.get_ltp(exchange=self.groww.EXCHANGE_NSE, exchange_trading_symbols="NSE_NIFTY")
            if ltp: return list(ltp.values())[0]
            
            return 0.0
        except:
            return 0.0

    def fetch_market_state(self):
        try:
            # 1. GET FUTURES (For Volume & VWAP)
            end = datetime.datetime.now(IST)
            start = end - datetime.timedelta(minutes=40) # Fetch more candles for rolling avg
            resp = self.groww.get_historical_candles(
                exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
                start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
                candle_interval="1minute"
            )
            if not resp or 'candles' not in resp: return None
            
            candles = resp['candles']
            df = pd.DataFrame(candles, columns=['t','o','h','l','c','v','oi'][:len(candles[0])])
            
            # VWAP & Volume
            df['vp'] = ((df['h'] + df['l'] + df['c']) / 3) * df['v']
            vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
            
            cur_vol = df['v'].iloc[-1]
            # NaN FIX: Fill NaN with 0 or the current volume to prevent crash
            avg_vol = df['v'].rolling(20).mean().fillna(cur_vol).iloc[-1] 
            vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 0
            fut_p = df['c'].iloc[-1]
            
            # 2. GET SPOT PRICE (For ATM Selection)
            spot_p = self.get_nifty_spot()
            if spot_p == 0: spot_p = fut_p # Fallback to Future if Spot fails
            
            # 3. DETERMINE TREND & TARGET
            # Logic: If Futures > VWAP -> Bullish. 
            # Reversal Logic: If Spot RSI is super low (<20) we might check Puts, but sticking to Trend for safety first.
            trend = "BULLISH" if fut_p > vwap else "BEARISH"
            
            if self.pos:
                sym = self.active_sym
                strike = 0
            else:
                target = "CE" if trend == "BULLISH" else "PE"
                strike = int(round(spot_p / 50) * 50) # Using SPOT for Strike
                chain = self.groww.get_option_chain(exchange="NSE", underlying="NIFTY", expiry_date=EXPIRY_DATE)
                s_data = chain['strikes'].get(str(strike), {}).get(target, {})
                sym = s_data.get("trading_symbol")

            if not sym: return None

            # 4. QUOTE DATA
            quote = self.groww.get_quote(exchange="NSE", segment="FNO", trading_symbol=sym)
            if not quote: return None

            curr_oi = quote.get("open_interest", 0)
            live_drop = self.get_symbol_specific_panic(sym, curr_oi)
            
            offer = quote.get("offer_price", 0.0) or 0.0
            bid = quote.get("bid_price", 0.0) or 0.0
            spread = offer - bid

            return {
                "spot_p": spot_p, "fut_p": fut_p, "vwap": vwap, 
                "vol_r": vol_ratio, "avg_vol": avg_vol, "trend": trend,
                "strike": strike, "sym": sym, "ltp": quote.get("last_price", 0),
                "oi": curr_oi, "panic": live_drop, "spr": spread,
                "type": "CE" if "CE" in sym else "PE"
            }

        except Exception as e:
            logger.warning(f"Sync Error: {e}")
            return None

    def start(self):
        logger.info("Sniper Active. Tracking NIFTY SPOT + FUTURES VOLUME...")
        while True:
            try:
                d = self.fetch_market_state()
                if not d: 
                    time.sleep(1); continue

                sig = "WAIT"
                current_pnl = 0.0

                # ENTRY
                if self.pos is None and self.trades < 5:
                    if (d['vol_r'] > VOL_MULTIPLIER) and \
                       (d['panic'] < OI_DROP_THRESHOLD) and \
                       (d['spr'] <= MAX_SPREAD):
                        
                        sig = f"BUY_{d['type']}"
                        self.pos = d['type']
                        self.active_sym = d['sym']
                        self.entry_p = d['ltp']
                        self.sl_p, self.high_p = self.entry_p - SL_POINTS, self.entry_p
                        self.trades += 1
                        
                        logger.info(f"ENTRY: {sig} {d['sym']} @ {self.entry_p} | Spot: {d['spot_p']}")
                        self.log_trade("BUY", self.entry_p, 0.0, "Panic_Entry")

                # EXIT
                elif self.pos:
                    current_pnl = (d['ltp'] - self.entry_p) * LOT_SIZE
                    
                    if d['ltp'] > self.high_p:
                        self.high_p = d['ltp']
                        if (self.high_p - self.entry_p) > TRAIL_TRIGGER:
                            self.sl_p = max(self.sl_p, self.high_p - TRAIL_GAP)
                    
                    if d['ltp'] <= self.sl_p:
                        sig = "EXIT"
                        final_pnl = (self.sl_p - self.entry_p) * LOT_SIZE
                        self.bal += final_pnl
                        
                        logger.info(f"EXIT: {self.active_sym} @ {self.sl_p} | PnL: {final_pnl}")
                        self.log_trade("SELL", self.sl_p, final_pnl, "Stop_Hit")
                        self.pos = None
                        self.active_sym = None

                # LOGGING
                ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
                with open(DATA_FILE, "a", newline='') as f:
                    # Fix: Safe int conversion for avg_vol
                    safe_avg_vol = int(d['avg_vol']) if not pd.isna(d['avg_vol']) else 0
                    
                    csv.writer(f).writerow([
                        ts, d['spot_p'], d['fut_p'], round(d['vwap'],2), 
                        round(d['vol_r'],2), d['trend'], d['strike'], d['sym'], d['ltp'], 
                        round(d['panic'],2), round(d['spr'],2),
                        sig, round(current_pnl,2), round(self.bal,2)
                    ])
                    f.flush()

                time.sleep(1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    HybridSniperV78().start()