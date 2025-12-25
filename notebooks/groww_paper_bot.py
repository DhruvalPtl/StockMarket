from growwapi import GrowwAPI
import pandas as pd
import pandas_ta as ta
import time
import datetime

# --- CONFIGURATION ---
API_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQzNTIwMzYsImlhdCI6MTc2NTk1MjAzNiwibmJmIjoxNzY1OTUyMDM2LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NzljMTAyNy03ZDQ1LTRlOWItYWM5ZS1iNDgzMWRiODQzZTFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjllODBhNjM2LTY4OGMtNDQ4OC1hMDhjLTU1NzQwMDQwNDMwZlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmM5ODU6OWEzNjo2ZTEyOjFjZWIsMTYyLjE1OC4yMzUuMjA0LDM1LjI0MS4yMy4xMjNcIixcInR3b0ZhRXhwaXJ5VHNcIjoyNTU0MzUyMDM2MzA0fSIsImlzcyI6ImFwZXgtYXV0aC1wcm9kLWFwcCJ9.vFYYnOrSLi-teVY6qhFF11SeSVZRIo-xBz_lVlOoTDujYw3ucWZSbOoP9sqFg11Oc8cCwWASqbg_R-9BfmPU0Q"  # <--- PASTE YOUR TOKEN HERE
CAPITAL = 10000.0     # Virtual Money
LOT_SIZE = 75

# SCALP SETTINGS
EMA_FAST_LEN = 5
EMA_SLOW_LEN = 13
SL_POINTS = 5.0       # Real Option Points
TRAIL_TRIGGER = 3.0   # Start trailing after 3 pts profit

# GLOBAL TRACKERS
groww = None
position = None       # 'CALL' or 'PUT' or None
entry_price = 0.0
sl_price = 0.0
highest_price = 0.0
trades_today = 0
daily_pnl = 0.0

def initialize_groww():
    global groww
    try:
        groww = GrowwAPI(API_TOKEN)
        print("✅ Connected to Groww API")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        exit()

def get_nifty_candles():
    """Fetches 5-minute candles for Nifty 50 to calculate EMA"""
    try:
        # Fetching historical data (Nifty 50 Index)
        # Note: You need the correct symbol or exchange_token for Nifty 50 Index
        # Usually it is "NIFTY 50" or similar. Checking documentation is recommended.
        candles = groww.get_historical_data(
            exchange=groww.EXCHANGE_NSE,
            trading_symbol="NIFTY 50", 
            interval=groww.INTERVAL_5MIN,
            segment=groww.SEGMENT_INDEX 
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df['close'] = df['close'].astype(float)
        
        # Calculate EMA
        df['EMA_Fast'] = ta.ema(df['close'], length=EMA_FAST_LEN)
        df['EMA_Slow'] = ta.ema(df['close'], length=EMA_SLOW_LEN)
        
        return df.iloc[-1] # Return the latest candle
    except Exception as e:
        print(f"Data Error: {e}")
        return None

def get_atm_option(nifty_price, type_):
    """Finds the ATM Option Symbol (e.g., NIFTY25JAN23000CE)"""
    # Round to nearest 50
    strike = round(nifty_price / 50) * 50
    
    # You would need logic here to construct the symbol dynamically 
    # based on the current expiry. For now, let's assume a function finds it.
    # In a real script, you'd use the option chain API:
    # chain = groww.get_option_chain(...)
    
    # Placeholder for the logic:
    symbol = f"NIFTY24JAN{strike}{type_}" 
    return symbol

def get_ltp(symbol):
    """Gets Live Price of the Option"""
    try:
        resp = groww.get_ltp(
            exchange=groww.EXCHANGE_NSE,
            trading_symbol=symbol,
            segment=groww.SEGMENT_FNO
        )
        return float(resp['ltp'])
    except:
        return 0.0

def main():
    global position, entry_price, sl_price, highest_price, trades_today, daily_pnl, CAPITAL

    initialize_groww()
    print(f"--- GROWW PAPER TRADER STARTED ---")
    print(f"Capital: ₹{CAPITAL}")
    print("Waiting for market data...\n")

    while True:
        # 1. Get Technicals (Nifty Spot)
        candle = get_nifty_candles()
        if candle is None:
            time.sleep(5)
            continue

        nifty_ltp = candle['close']
        ema_f = candle['EMA_Fast']
        ema_s = candle['EMA_Slow']
        
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        status = f"[{current_time}] Nifty: {nifty_ltp:.2f} | Fast: {ema_f:.2f} | Slow: {ema_s:.2f}"

        # 2. Entry Logic
        if position is None:
            if trades_today >= 5:
                print("Max trades reached.")
                time.sleep(60)
                continue

            # BUY CALL
            if ema_f > ema_s:
                print(f"\n🚀 SIGNAL: BUY CALL (Nifty {nifty_ltp})")
                
                # Find Option
                atm_symbol = get_atm_option(nifty_ltp, "CE")
                option_price = get_ltp(atm_symbol)
                
                if option_price > 0:
                    position = 'CALL'
                    entry_price = option_price
                    sl_price = entry_price - SL_POINTS
                    highest_price = entry_price
                    print(f"✅ VIRTUAL ENTRY: {atm_symbol} @ ₹{entry_price}")
                    print(f"🛑 SL: {sl_price}")

            # BUY PUT
            elif ema_f < ema_s:
                print(f"\n🚀 SIGNAL: BUY PUT (Nifty {nifty_ltp})")
                
                atm_symbol = get_atm_option(nifty_ltp, "PE")
                option_price = get_ltp(atm_symbol)
                
                if option_price > 0:
                    position = 'PUT'
                    entry_price = option_price
                    sl_price = entry_price - SL_POINTS
                    highest_price = entry_price
                    print(f"✅ VIRTUAL ENTRY: {atm_symbol} @ ₹{entry_price}")
                    print(f"🛑 SL: {sl_price}")
            
            else:
                print(f"{status} | Waiting...", end='\r')

        # 3. Manage Trade
        else:
            # Get Live Option Price
            # (In real code, verify we track the same symbol we bought)
            current_opt_price = get_ltp(atm_symbol) 
            pnl = (current_opt_price - entry_price) * LOT_SIZE
            
            print(f"{status} | PnL: ₹{pnl:.2f} | LTP: {current_opt_price}      ", end='\r')

            # Trailing
            if current_opt_price > highest_price:
                highest_price = current_opt_price
                if (highest_price - entry_price) > TRAIL_TRIGGER:
                    new_sl = highest_price - 4.0
                    if new_sl > sl_price: sl_price = new_sl

            # Check Exit
            if current_opt_price <= sl_price:
                print(f"\n🛑 STOP HIT! Exit @ {sl_price}")
                CAPITAL += (sl_price - entry_price) * LOT_SIZE
                daily_pnl += (sl_price - entry_price) * LOT_SIZE
                position = None
                trades_today += 1
                print(f"New Balance: ₹{CAPITAL:.2f}\n")

        time.sleep(1) # Check every second

if __name__ == "__main__":
    main()