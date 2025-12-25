import time
from groww_data_pipeline import GrowwDataEngine

# ===========================
# 🔧 USER SETTINGS
# ===========================
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ3OTEyNzAsImlhdCI6MTc2NjM5MTI3MCwibmJmIjoxNzY2MzkxMjcwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIyNzZlNGNhYy0yZTgyLTQzYTUtYjA4Yi03ZmNiYmMzZmIwNzJcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjRlZjFjNjcxLTM4MjMtNDUyYi1iMDAzLWExOGRmMGQxNDEyYlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjY4Yzk6OWQ4NToyNThlOjI2YywxNzIuNzAuMTgzLjE2NCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDc5MTI3MDU2OX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.IH0-H1Ub186gc1ZZkmkTnQaWw9fXlrdYfKMkzCTAd23ReOLdaB6JNuTMylXVW6gBGZv4X6G1t-2NJKjcapq4wg"
API_SECRET = "6EY2&DYgrhcxa2IBoeG7-il_cNc2UTaS"
EXPIRY     = "2025-12-30" 
FUT_SYM    = "NSE-NIFTY-30Dec25-FUT"

# 1. INITIALIZE ENGINE (It creates the CSV automatically)
engine = GrowwDataEngine(API_KEY, API_SECRET, EXPIRY, FUT_SYM)

print("⏳ Engine Warming Up... (Check CSV file in folder)")

while True:
    time.sleep(1)
    
    # 2. UPDATE (Fetches Data & Saves to CSV)
    engine.update()
    
    # 3. PRINT FOR VISUAL CONFIRMATION
    print(f"[{engine.timestamp}] Spot: {engine.spot_ltp} | RSI: {int(engine.rsi)} | ATM: {engine.atm_strike} | CE: {engine.atm_ce['ltp']} | PE: {engine.atm_pe['ltp']} | PCR: {engine.pcr}", end='\r')