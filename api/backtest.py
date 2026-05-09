"""API endpoint: backtest a ticker with the EMA crossover strategy."""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
import pandas as pd
import numpy as np


def get_data(ticker, period="5y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": period, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    data = r.json()["chart"]["result"][0]
    ohlcv = data["indicators"]["quote"][0]
    df = pd.DataFrame({
        "Open": ohlcv["open"], "High": ohlcv["high"],
        "Low": ohlcv["low"], "Close": ohlcv["close"],
        "Volume": ohlcv["volume"],
    }, index=pd.to_datetime(data["timestamp"], unit="s"))
    return df.dropna()


def backtest(ticker, period="5y"):
    """Simple backtest: 200 SMA + 50 EMA cross, 20% trailing stop."""
    df = get_data(ticker, period)
    if len(df) < 200:
        return {"error": "insufficient data"}

    closes = df["Close"].values
    sma200 = pd.Series(closes).rolling(200).mean().values
    ema50 = pd.Series(closes).ewm(span=50, adjust=False).mean().values

    cash = 5000.0
    shares = 0.0
    highest = 0.0
    trades = []

    for i in range(201, len(closes)):
        if shares == 0:
            if (closes[i] > sma200[i] and closes[i] > ema50[i] and closes[i - 1] <= ema50[i - 1]):
                shares = (cash * 0.95) / closes[i]
                entry_price = closes[i]
                cash -= shares * closes[i]
                highest = closes[i]
        else:
            highest = max(highest, closes[i])
            if closes[i] < highest * 0.80:
                cash += shares * closes[i]
                trades.append({
                    "entry": round(entry_price, 2),
                    "exit": round(closes[i], 2),
                    "return_pct": round((closes[i] / entry_price - 1) * 100, 1),
                })
                shares = 0
                highest = 0

    # Close open position
    if shares > 0:
        cash += shares * closes[-1]
        trades.append({
            "entry": round(entry_price, 2),
            "exit": round(closes[-1], 2),
            "return_pct": round((closes[-1] / entry_price - 1) * 100, 1),
        })

    total_return = (cash / 5000 - 1) * 100
    buy_hold = (closes[-1] / closes[200] - 1) * 100
    wins = [t for t in trades if t["return_pct"] > 0]

    return {
        "ticker": ticker,
        "period": period,
        "return_pct": round(total_return, 1),
        "buy_hold_pct": round(buy_hold, 1),
        "num_trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "trades": trades[-10:],  # last 10 trades
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = parse_qs(urlparse(self.path).query)
            ticker = params.get("ticker", ["AVGO"])[0].upper()
            period = params.get("period", ["5y"])[0]

            result = backtest(ticker, period)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
