"""
Test option chain API to understand expected format
"""
import sys
import os
import json
import requests
import urllib.parse

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig

# Let's test the API directly
host = 'https://piconnect.flattrade.in/PiConnectTP'
endpoint = '/GetOptionChain'
url = f"{host}{endpoint}"

username = BotConfig.USER_ID
susertoken = BotConfig.USER_TOKEN


print("Testing Option Chain API Directly")
print("=" * 60)

test_cases = [
    ("NIFTY13JAN26", "26000"),  # Valid strike
    ("NIFTY13JAN26", "25900"),  # Another strike
    ("NIFTY13JAN26C26000", "26000"),  # With option type
    ("NIFTY", "26000"),  # Just NIFTY
]

for tradingsymbol, strikeprice in test_cases:
    print(f"\n🧪 Testing: {tradingsymbol}, Strike: {strikeprice}")
    print("-" * 60)
    
    values = {}
    values["uid"] = username
    values["exch"] = "NFO"
    values["tsym"] = urllib.parse.quote_plus(tradingsymbol)       
    values["strprc"] = str(strikeprice)
    values["cnt"] = "5"
    
    payload = 'jData=' + json.dumps(values) + f'&jKey={susertoken}'
    
    print(f"Sending: {payload[:100]}...")
    
    res = requests.post(url, data=payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text[:800]}")
    
    try:
        resDict = json.loads(res.text)
        if 'stat' in resDict:
            print(f"Stat: {resDict.get('stat')}")
            if 'emsg' in resDict:
                print(f"Error Msg: {resDict.get('emsg')}")
            if 'values' in resDict:
                print(f"Values Count: {len(resDict['values'])}")
                if resDict['values']:
                    print(f"\nFirst 2 Items:")
                    for i, item in enumerate(resDict['values'][:2]):
                        print(f"  [{i}] {json.dumps(item, indent=4)[:400]}")
    except Exception as e:
        print(f"Parse Error: {e}")


