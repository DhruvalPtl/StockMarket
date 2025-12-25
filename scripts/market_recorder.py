import time
import csv
import os
from datetime import datetime
from groww_data_pipeline import GrowwDataEngine

# CONFIGURATION
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ5NTMwMzAsImlhdCI6MTc2NjU1MzAzMCwibmJmIjoxNzY2NTUzMDMwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI3NTc2NzhiMS1mYjQxLTRkZjgtODc5Zi0yMDc3NTI2MTI5YzFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjEwYzcxYzg2LWM2NzYtNDRhMS05N2VmLTc0N2EzYzdmMTM3Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OmFkNDU6YzJiZDo2ZmZhOjJjNDksMTcyLjcwLjIxOC41MSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDk1MzAzMDAwNX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.qfClpvX56UsEn5qeLufKny_uF8ztmx0TA8WL2_FD_pLcv1l7kMkgec8lw997gwqHLXPu6YJPzdn4ECjXUwhYqQ"
API_SECRET = "84ENDHT5g1DQE86e2k8(Of*s4ukp!Ari"
EXPIRY     = "2025-12-30" # Update this weekly

class MarketRecorder:
    def __init__(self):
        self.engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY)
        
        # Create a filename with today's date
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.filename = f"D:\\StockMarket\\StockMarket\\scripts\\market_recorder\\Nifty_ACTUAL_Data_{date_str}.csv"
        
        # Initialize CSV with Headers if it doesn't exist
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                # WE SAVE EVERYTHING YOU NEED FOR A PERFECT BACKTEST
                writer.writerow([
                    "Datetime", "Spot_Price", "Velocity", 
                    "ATM_CE_Symbol", "ATM_CE_Price", "ATM_CE_Delta", 
                    "ATM_PE_Symbol", "ATM_PE_Price", "ATM_PE_Delta"
                ])
        print(f"🔴 RECORDING LIVE DATA TO: {self.filename}")
        
        self.last_spot = 0

    def run(self):
        print("⏳ Waiting for Market Data...")
        while True:
            try:
                self.engine.update()
                
                # Calculate Velocity Live
                spot = self.engine.spot_ltp
                velocity = abs(spot - self.last_spot) if self.last_spot != 0 else 0
                self.last_spot = spot
                
                if spot == 0: continue # Skip empty ticks

                # THE ACTUAL DATA ROW
                row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    spot,
                    round(velocity, 2),
                    self.engine.atm_ce['symbol'],
                    self.engine.atm_ce['ltp'],
                    self.engine.atm_ce['delta'],  # <--- THIS IS THE ACTUAL DELTA YOU WANT
                    self.engine.atm_pe['symbol'],
                    self.engine.atm_pe['ltp'],
                    self.engine.atm_pe['delta']   # <--- ACTUAL PUT DELTA
                ]

                # Save to File
                with open(self.filename, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)

                print(f"REC: {row[0]} | Spot: {spot} | Delta: {row[5]}", end='\r')
                
                time.sleep(1) # Record every 1 second

            except KeyboardInterrupt:
                print("\n🛑 Recording Stopped.")
                break
            except Exception as e:
                print(f"\n⚠️ Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    MarketRecorder().run()