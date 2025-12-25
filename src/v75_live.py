# @title V75 - Industrial Sniper (With Dedicated Trade Journal)
import logging
import csv
import os
import sys
import time
import datetime
import pandas as pd
import pytz
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
OI_DROP_THRESHOLD = -2.0  
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
logger = logging.getLogger("V75")

# Files
DATA_FILE = "V75_Master_BlackBox.csv"    # The Heartbeat (Every Second)
TRADE_FILE = "V75_Trade_Journal.csv"     # The Money (Only Trades)

class IndustrialSniperV75:
    def __init__(self):
        self.groww = None
        self.pos = None 
        self.active_sym = "N/A"
        self.entry_p = 0.0
        self.sl_p = 0.0
        self.high_p = 0.0
        self.bal = START_BALANCE
        self.trades = 0
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
        # 1. Master Data Log
        if not os.path.isfile(DATA_FILE):
            with open(DATA_FILE, "w", newline='') as f:
                csv.writer(f).writerow([
                    "Timestamp", "Fut_Price", "Fut_VWAP", "Vol_Ratio", "Trend",
                    "Strike", "Opt_Symbol", "Opt_LTP", "OI_Chg", "Spread",
                    "Signal", "PnL", "Balance"
                ])
        
        # 2. Trade Journal (The New File)
        if not os.path.isfile(TRADE_FILE):
            with open(TRADE_FILE, "w", newline='') as f:
                csv.writer(f).writerow(["Time", "Action", "Symbol", "Price", "PnL", "Reason"])
            logger.info(f"Created Trade Journal: {TRADE_FILE}")

    def log_trade(self, action, price, pnl, reason):
        """Writes only executed trades to the Journal"""
        ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
        with open(TRADE_FILE, "a", newline='') as f:
            csv.writer(f).writerow([ts, action, self.active_sym, price, pnl, reason])
            f.flush()

    def fetch_market_state(self):
        try:
            # 1. FUTURES
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
            df = pd.DataFrame(candles, columns=['t','o','h','l','c','v','oi'][:len(candles[0])])
            df['vp'] = ((df['h'] + df['l'] + df['c']) / 3) * df['v']
            vwap = df['vp'].cumsum().iloc[-1] / df['v'].cumsum().iloc[-1]
            vol_ratio = df['v'].iloc[-1] / df['v'].rolling(20).mean().iloc[-1]
            fut_p = df['c'].iloc[-1]

            # 2. OPTION MAPPING
            trend = "BULLISH" if fut_p > vwap else "BEARISH"
            target = "CE" if trend == "BULLISH" else "PE"
            strike = int(round(fut_p / 50) * 50)

            # 3. CHAIN & QUOTE
            chain = self.groww.get_option_chain(exchange="NSE", underlying="NIFTY", expiry_date=EXPIRY_DATE)
            s_data = chain['strikes'].get(str(strike), {}).get(target, {})
            sym = s_data.get("trading_symbol")
            if not sym: return None

            quote = self.groww.get_quote(exchange="NSE", segment="FNO", trading_symbol=sym)
            if not quote: return None

            # Safe Spread Calc
            offer = quote.get("offer_price") if quote.get("offer_price") else 0.0
            bid = quote.get("bid_price") if quote.get("bid_price") else 0.0
            spread = offer - bid

            return {
                "fut_p": fut_p, "vwap": vwap, "vol_r": vol_ratio, "trend": trend, 
                "strike": strike, "sym": sym, "ltp": quote.get("last_price", 0),
                "oi_c": quote.get("oi_day_change_percentage", 0),
                "spr": spread, "type": target
            }
        except Exception as e:
            logger.warning(f"Data Syncing... ({e})")
            return None

    def start(self):
        logger.info("Sniper Active. Waiting for signals...")
        while True:
            try:
                d = self.fetch_market_state()
                if not d: 
                    time.sleep(1); continue

                sig = "WAIT"
                current_pnl = 0.0

                # ENTRY
                if self.pos is None and self.trades < 3:
                    if (d['vol_r'] > VOL_MULTIPLIER) and (d['oi_c'] < OI_DROP_THRESHOLD) and (d['spr'] <= MAX_SPREAD):
                        sig = f"BUY_{d['type']}"
                        self.pos, self.active_sym, self.entry_p = d['type'], d['sym'], d['ltp']
                        self.sl_p, self.high_p = self.entry_p - SL_POINTS, self.entry_p
                        self.trades += 1
                        
                        logger.info(f"ENTRY: {sig} @ {self.entry_p} | OI Panic: {d['oi_c']}%")
                        self.log_trade("BUY", self.entry_p, 0.0, "Signal_Entry")

                # EXIT / TRAIL
                elif self.pos:
                    current_pnl = (d['ltp'] - self.entry_p) * LOT_SIZE
                    
                    # Trail
                    if d['ltp'] > self.high_p:
                        self.high_p = d['ltp']
                        if (self.high_p - self.entry_p) > TRAIL_TRIGGER:
                            self.sl_p = max(self.sl_p, self.high_p - TRAIL_GAP)
                    
                    # Stop Hit
                    if d['ltp'] <= self.sl_p:
                        sig = "EXIT"
                        final_pnl = (self.sl_p - self.entry_p) * LOT_SIZE
                        self.bal += final_pnl
                        
                        logger.info(f"EXIT: @ {self.sl_p} | PnL: {final_pnl}")
                        self.log_trade("SELL", self.sl_p, final_pnl, "Stop/Trail_Hit")
                        self.pos = None

                # HEARTBEAT LOG (Every Second)
                ts = datetime.datetime.now(IST).strftime("%H:%M:%S")
                with open(DATA_FILE, "a", newline='') as f:
                    csv.writer(f).writerow([
                        ts, d['fut_p'], round(d['vwap'],2), round(d['vol_r'],2), d['trend'],
                        d['strike'], d['sym'], d['ltp'], round(d['oi_c'],2), round(d['spr'],2),
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
    IndustrialSniperV75().start()