from growwapi import GrowwAPI
import sys

# 🚨 PASTE KEYS CAREFULLY HERE
API_KEY    = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTQ3OTEyNzAsImlhdCI6MTc2NjM5MTI3MCwibmJmIjoxNzY2MzkxMjcwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIyNzZlNGNhYy0yZTgyLTQzYTUtYjA4Yi03ZmNiYmMzZmIwNzJcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiMDdmMDA0MGMtZTk4Zi00ZDNmLTk5Y2EtZDc1ZjBlYWU5M2NlXCIsXCJkZXZpY2VJZFwiOlwiZDMyMWIxMzUtZWQ5Mi01ZWJkLWJjMDUtZTY1NDY2OWRiMDM5XCIsXCJzZXNzaW9uSWRcIjpcIjRlZjFjNjcxLTM4MjMtNDUyYi1iMDAzLWExOGRmMGQxNDEyYlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1yOE5XVzhzdTNvZ080am1ZUzIwZEpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA5OjQwOTA6MTA4ZjpkYzA1OjY4Yzk6OWQ4NToyNThlOjI2YywxNzIuNzAuMTgzLjE2NCwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU1NDc5MTI3MDU2OX0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.IH0-H1Ub186gc1ZZkmkTnQaWw9fXlrdYfKMkzCTAd23ReOLdaB6JNuTMylXVW6gBGZv4X6G1t-2NJKjcapq4wg"
API_SECRET = "6EY2&DYgrhcxa2IBoeG7-il_cNc2UTaS"

print(f"Testing Login...")
print(f"Key Length: {len(API_KEY)}")
print(f"Secret Length: {len(API_SECRET)}")

try:
    # 1. Try cleaning the keys (Fixes copy-paste errors)
    clean_key = API_KEY.strip()
    clean_secret = API_SECRET.strip()
    
    # 2. Attempt Login
    print("👉 Sending Request...")
    token = GrowwAPI.get_access_token(api_key=API_KEY, secret=API_SECRET)
    
    if token:
        print("✅ SUCCESS! Token received.")
        print(f"Token: {token[:10]}...")
    else:
        print("❌ FAILED. Token is None.")

except Exception as e:
    print(f"❌ CRITICAL ERROR: {e}")
    # If 400, it means the Key/Secret string format is rejected by server