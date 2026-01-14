import sys
sys.path.insert(0, 'D:/StockMarket/StockMarket/scripts/claude/pythonAPI-main')
sys.path.insert(0, 'D:/StockMarket/StockMarket/scripts/claude/pythonAPI-main/dist')

from api_helper import NorenApiPy
import config

api = NorenApiPy()
api.set_session(config.BotConfig.USER_ID, '', config.BotConfig.USER_TOKEN)

# Search for 25700 strike
results = api.searchscrip('NFO', 'NIFTY 25700')
print('Results type:', type(results))
print('Results:', results)

# Search for 13JAN26 options
results = api.searchscrip('NFO', 'NIFTY13JAN26C25700')
print('\nDirect symbol search NIFTY13JAN26C25700:')
print('Results:', results)
