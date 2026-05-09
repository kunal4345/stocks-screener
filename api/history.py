"""API endpoint: shows past picks and their performance since recommendation."""

import json
import os
import requests
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path


def get_current_price(ticker):
    """Get current price from Yahoo."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        r = requests.get(url, params={"range": "5d", "interval": "1d"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code != 200:
            return None
        closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        return closes[-1] if closes else None
    except Exception:
        return None


def load_history():
    """Load all history JSON files, return sorted by date desc."""
    history_dir = Path(__file__).parent.parent / "history"
    if not history_dir.exists():
        return []

    entries = []
    for f in sorted(history_dir.glob("*.json"), reverse=True)[:14]:  # Last 14 days
        try:
            data = json.loads(f.read_text())
            date_str = f.stem  # e.g. "2026-05-08"
            picks = data.get("picks", [])
            if picks:
                entries.append({"date": date_str, "picks": picks})
        except Exception:
            continue
    return entries


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            history = load_history()

            # Get current prices for most recent picks to show performance
            if history:
                recent = history[0]
                for pick in recent["picks"][:5]:  # Price check top 5
                    current = get_current_price(pick["ticker"])
                    if current and pick.get("price"):
                        pick["current_price"] = round(current, 2)
                        pick["gain_pct"] = round((current / pick["price"] - 1) * 100, 1)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "history": history[:7],  # Last 7 days
                "count": len(history),
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e), "history": []}).encode())
