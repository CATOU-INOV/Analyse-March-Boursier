import sys
import yfinance as yf
import json

def get_stock_data(tickers):
    data = []
    for ticker in tickers:
        stock = yf.Ticker(ticker)
        
        # Récupérer les 10 derniers jours
        hist = stock.history(period="100d")  
        hist.reset_index(inplace=True)
        info = stock.info
        company_name = info.get("longName", ticker)

        if not hist.empty:
            for index, row in hist.iterrows():
                date_value = row["Date"].date()
                open_price = float(row["Open"])
                close_price = float(row["Close"])
                high_price = float(row["High"])
                low_price = float(row["Low"])
                volume = int(row["Volume"])
                dividends = float(row["Dividends"]) if "Dividends" in hist.columns else 0.0
                stock_splits = float(row["Stock Splits"]) if "Stock Splits" in hist.columns else 0.0

                data.append({
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
                })
        else:
            data.append({
                "ticker": ticker,
                "company_name": "No data available",
                "date": "",
                "open_price": 0.0,
                "close_price": 0.0,
                "high_price": 0.0,
                "low_price": 0.0,
                "volume": 0,
                "dividends": 0.0,
                "stock_splits": 0.0
            })
    
    return data

tickers = ["AAPL", "GOOGL", "TSLA"]
try:
    stock_data = get_stock_data(tickers)
    print(json.dumps(stock_data, indent=4))
except SystemExit:
    pass

