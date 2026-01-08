"""
Check what data fields are available in option chain API response
"""
import sys
import os
import json
import requests
import urllib.parse

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import BotConfig

# Test what fields are available
host = 'https://piconnect.flattrade.in/PiConnectTP'
endpoint = '/GetOptionChain'
url = f"{host}{endpoint}"

username = BotConfig.USER_ID
susertoken = BotConfig.USER_TOKEN

# Try to get option chain data with live prices
tradingsymbol = "NIFTY13JAN26C26150"
strikeprice = "26150"

values = {}
values["uid"] = username
values["exch"] = "NFO"
values["tsym"] = urllib.parse.quote_plus(tradingsymbol)       
values["strprc"] = str(strikeprice)
values["cnt"] = "5"

payload = 'jData=' + json.dumps(values) + f'&jKey={susertoken}'

res = requests.post(url, data=payload)
resDict = json.loads(res.text)

if resDict.get('stat') == 'Ok' and 'values' in resDict:
    print("✅ Got option chain data!")
    print(f"\nTotal items: {len(resDict['values'])}")
    print("\nSample CE option:")
    
    # Find a CE option
    for item in resDict['values']:
        if item.get('optt') == 'CE':
            print(json.dumps(item, indent=2))
            print(f"\nFields available: {list(item.keys())}")
            break
    
    print("\n\nSample PE option:")
    # Find a PE option
    for item in resDict['values']:
        if item.get('optt') == 'PE':
            print(json.dumps(item, indent=2))
            break
    
    # Now try to get quotes for an individual option
    print("\n\n=== Testing get_quotes for individual option ===")
    token = resDict['values'][0]['token']
    print(f"Trying token: {token}")
    
    # Try get_quotes endpoint
    quote_url = f"{host}/GetQuotes"
    quote_values = {}
    quote_values["uid"] = username
    quote_values["exch"] = "NFO"
    quote_values["token"] = token
    
    quote_payload = 'jData=' + json.dumps(quote_values) + f'&jKey={susertoken}'
    quote_res = requests.post(quote_url, data=quote_payload)
    quote_dict = json.loads(quote_res.text)
    
    print(f"Quote response: {json.dumps(quote_dict, indent=2)[:500]}")

