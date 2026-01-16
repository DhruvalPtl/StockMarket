import zipfile
with zipfile.ZipFile("D:\\StockMarket\\StockMarket\\scripts\\claude\\experiment8\\pythonAPI-main\\pythonAPI-main\\dist\\NorenRestApi-0.0.29-py3-none-any.whl", "r") as f:
    f.extractall("D:\\StockMarket\\StockMarket\\scripts\\claude\\experiment8\\unpacked_whl")
