# @title V77 - Intelligent Sniper (Strike Memory & Trade Lock)
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
OI_DROP_THRESHOLD = -1.0  # -1% drop in 3 minutes
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
logger = logging.getLogger("V77")

# Files
DATA_FILE = "V77_Live_Log1.csv"
TRADE_FILE = "V77_Trade_Journal1.csv"

class IntelligentSniperV77:
    def __init__(self):
        self.groww = None
        self.pos = None        # "CE" or "PE"
        self.active_sym = None # Stores the exact symbol we bought
        self.entry_p = 0.0
        self.sl_p = 0.0
        self.high_p = 0.0
        self.bal = START_BALANCE
        self.trades = 0
        
        # FIX: Dictionary of Deques to separate history by Symbol
        # { "NIFTY26000CE": [(ts, oi), ...], "NIFTY26050CE": [...] }
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
                    "Timestamp", "Fut_Price", "VWAP", "Vol", "Avg_Vol", "Trend",
                    "Strike", "Opt_Symbol", "Opt_LTP", "Current_OI", 
                    "3min_OI_Drop%", "Spread", "Signal", "PnL", "Balance"
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
        """Calculates OI drop ONLY for the specific symbol history"""
        now = time.time()
        # Add to specific symbol history
        self.oi_memory[symbol].append((now, current_oi))
        
        # Retrieve specific symbol history
        history = self.oi_memory[symbol]
        
        old_oi = current_oi
        for ts, oi in history:
            if now - ts >= 180: # 3 mins ago
                old_oi = oi
                break
        
        if old_oi == 0: return 0.0
        return ((current_oi - old_oi) / old_oi) * 100

    def fetch_market_state(self):
        # Retry Logic for "Internal Error"
        for attempt in range(3):
            try:
                # 1. FUTURES (Trend & Volume)
                end = datetime.datetime.now(IST)
                start = end - datetime.timedelta(minutes=30)
                resp = self.groww.get_historical_candles(
                    exchange="NSE", segment="FNO", groww_symbol=FUTURES_SYMBOL,
                    start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
                    end_time=end.strftime("%Y-%m-%d %H:%M:%S"),
                    candle_interval="1minute"
                )
                if not resp or 'candles' not in resp: 
                    time.sleep(1); continue
                
                candles = resp['candles']
                df = pd.DataFrame(candles, columns=['t','o','h','l','c','v','oi'][:len(candles[0])])
                
                # VWAP Calc
                df['vp'] = ((df['h'] + df['l'] + df['c']) / 3) * df['v']
                vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
                
                # Volume Average Calc (Explains Q2)
                cur_vol = df['v'].iloc[-1]
                avg_vol = df['v'].rolling(20).mean().iloc[-1]
                vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 0
                fut_p = df['c'].iloc[-1]

                # 2. SELECT SYMBOL (Explains Q3)
                trend = "BULLISH" if fut_p > vwap else "BEARISH"
                
                # IF WE HAVE A POSITION, WE MUST TRACK THAT SPECIFIC SYMBOL
                if self.pos:
                    sym = self.active_sym
                    # We don't care about strike calculation, we track what we own
                    strike = 0 
                else:
                    # SCANNING MODE: Calculate fresh ATM
                    target = "CE" if trend == "BULLISH" else "PE"
                    strike = int(round(fut_p / 50) * 50)
                    chain = self.groww.get_option_chain(exchange="NSE", underlying="NIFTY", expiry_date=EXPIRY_DATE)
                    s_data = chain['strikes'].get(str(strike), {}).get(target, {})
                    sym = s_data.get("trading_symbol")

                if not sym: return None

                # 3. GET QUOTE
                quote = self.groww.get_quote(exchange="NSE", segment="FNO", trading_symbol=sym)
                if not quote: return None

                curr_oi = quote.get("open_interest", 0)
                
                # FIX: Use Symbol-Specific Panic Calc
                live_drop = self.get_symbol_specific_panic(sym, curr_oi)

                offer = quote.get("offer_price", 0.0) or 0.0
                bid = quote.get("bid_price", 0.0) or 0.0
                spread = offer - bid

                return {
                    "fut_p": fut_p, "vwap": vwap, "vol": cur_vol, "avg_vol": avg_vol,
                    "trend": trend, "strike": strike, "sym": sym, 
                    "ltp": quote.get("last_price", 0),
                    "oi": curr_oi, "panic": live_drop, "spr": spread,
                    "type": "CE" if "CE" in sym else "PE"
                }

            except Exception as e:
                if attempt == 2: logger.warning(f"Data Sync Error: {e}")
                time.sleep(0.5)
        return None

    def start(self):
        logger.info("Sniper Active. Tracking Symbol-Specific Panic...")
        while True:
            try:
                d = self.fetch_market_state()
                if not d: 
                    time.sleep(1); continue

                sig = "WAIT"
                current_pnl = 0.0

                # ENTRY LOGIC
                if self.pos is None and self.trades < 3:
                    # Rule 1: Volume Spike
                    # Rule 2: Panic Drop (-1% in 3min) for THIS symbol
                    # Rule 3: Spread Check
                    if (d['vol'] > d['avg_vol'] * VOL_MULTIPLIER) and \
                       (d['panic'] < OI_DROP_THRESHOLD) and \
                       (d['spr'] <= MAX_SPREAD):
                        
                        sig = f"BUY_{d['type']}"
                        self.pos = d['type']
                        self.active_sym = d['sym'] # LOCK THE SYMBOL
                        self.entry_p = d['ltp']
                        self.sl_p, self.high_p = self.entry_p - SL_POINTS, self.entry_p
                        self.trades += 1
                        
                        logger.info(f"ENTRY: {sig} {d['sym']} @ {self.entry_p} | Panic: {d['panic']:.2f}%")
                        self.log_trade("BUY", self.entry_p, 0.0, "Panic_Entry")

                # EXIT LOGIC (Tracking Locked Symbol)
                elif self.pos:
                    # d['ltp'] is now guaranteed to be the locked symbol price
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
                    csv.writer(f).writerow([
                        ts, d['fut_p'], round(d['vwap'],2), d['vol'], int(d['avg_vol']), d['trend'],
                        d['strike'], d['sym'], d['ltp'], d['oi'], 
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
    IntelligentSniperV77().start()