from datetime import datetime
expiry = "2025-12-30"
dt = datetime.strptime(expiry, "%Y-%m-%d")
print(f"NSE-NIFTY-{dt.strftime('%d%b%y')}-FUT")
print(" Actual: NSE-NIFTY-30Dec25-FUT")