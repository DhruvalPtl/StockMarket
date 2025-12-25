import pandas as pd
print("nifty_1m.csv head:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\nifty_1m.csv", low_memory=False).head())
print("nifty_1m.csv tail:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\nifty_1m.csv", low_memory=False).tail())

print("groww_instruments.csv head:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\groww_instruments.csv", low_memory=False).head())
print("groww_instruments.csv tail:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\groww_instruments.csv", low_memory=False).tail())

print("option_ltp_1m.csv head:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\option_ltp_1m.csv", low_memory=False).head())
print("option_ltp_1m.csv tail:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\option_ltp_1m.csv", low_memory=False).tail())

print("option_chain_1m.csv head:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\option_chain_1m.csv", low_memory=False).head())
print("option_chain_1m.csv tail:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\option_chain_1m.csv", low_memory=False).tail())

print("nifty_spot_1m.csv head:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\nifty_spot_1m.csv", low_memory=False).head())
print("nifty_spot_1m.csv tail:")
print(pd.read_csv("D:\\StockMarket\\StockMarket\\data\\nifty_spot_1m.csv", low_memory=False).tail())
