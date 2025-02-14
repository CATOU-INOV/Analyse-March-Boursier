import sys
import yfinance as yf
import json

def get_stock_data(tickers):
    data = {}
    for ticker in tickers:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        hist.reset_index(inplace=True)
        info = stock.info
        company_name = info.get("longName", ticker)
        if not hist.empty:
            date_value = hist["Date"].iloc[0].date()
            open_price = float(hist["Open"].iloc[0])
            close_price = float(hist["Close"].iloc[0])
            high_price = float(hist["High"].iloc[0])
            low_price = float(hist["Low"].iloc[0])
            volume = int(hist["Volume"].iloc[0])
            dividends = float(hist["Dividends"].iloc[0]) if "Dividends" in hist.columns else 0.0
            stock_splits = float(hist["Stock Splits"].iloc[0]) if "Stock Splits" in hist.columns else 0.0
            data[ticker] = {
                "ticker": ticker,
                "company_name": company_name,
                "date": str(date_value),  
                "open_price": open_price,
                "close_price": close_price,
                "high_price": high_price,
                "low_price": low_price,
                "volume": volume,
                "dividends": dividends,
                "stock_splits": stock_splits
            }
        else:
            data[ticker] = "No data available"
    return data


tickers = ["AAPL", "GOOGL", "TSLA"]
try:
      stock_data = get_stock_data(tickers)
      print(json.dumps(stock_data)) 
except SystemExit:
    pass  
