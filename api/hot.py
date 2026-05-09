"""API endpoint: Hot Picks — analyst upgrades + momentum + Reddit buzz (low weight)."""

import json
import re
import os
import requests
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")

# Common words to exclude from Reddit ticker detection
NOISE = frozenset(
    "THE AND FOR ARE BUT NOT YOU ALL CAN HER WAS ONE OUR OUT HAS ITS CEO IPO ETF WSB DD "
    "YOLO IMO FYI PSA TIL EPS ATH GDP SEC FDA FED CPI US UK EU PM AM OP IV OTM ITM DTE "
    "LMAO WTF RIP LOL CFO COO CTO NYSE EDIT TLDR FWIW IIRC TBH SMH HODL MOASS FOMO FUD "
    "NEW NOW MAY JUST BEEN WILL WHAT THIS THAT WITH FROM HAVE THEY SOME THAN VERY MUCH "
    "ALSO OVER ONLY EVEN MOST BACK INTO YEAR WHEN YOUR MAKE LIKE LONG LOOK MANY THEN "
    "THEM EACH WELL MORE MADE AFTER COULD WOULD ABOUT WHERE BEING STILL GOING EVERY "
    "THOSE SINCE THEIR OTHER WHICH THESE FIRST THINK MIGHT SHOULD REALLY PEOPLE MARKET "
    "STOCK STOCKS MONEY PRICE SHARE TRADE SELL HOLD CALL PUTS BULL BEAR AI".split()
)


def get_analyst_picks():
    """Get stocks recently upgraded with strong buy + above SMA200."""
    from finvizfinance.screener.overview import Overview

    foverview = Overview()
    filters = {
        "Market Cap.": "+Mid (over $2bln)",
        "Analyst Recom.": "Strong Buy (1)",
        "200-Day Simple Moving Average": "Price above SMA200",
        "EPS growththis year": "Positive (>0%)",
    }
    foverview.set_filter(filters_dict=filters)
    df = foverview.screener_view()
    if df is None or df.empty:
        return {}
    # Return dict: ticker -> score contribution
    return {t: 40 for t in df["Ticker"].tolist()}


def get_reddit_mentions():
    """Scrape Reddit for ticker mentions. Returns dict: ticker -> mention count."""
    tickers = {}
    headers = {"User-Agent": "StockScreener/1.0"}

    for sub in ["wallstreetbets", "stocks", "investing"]:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=50",
                headers=headers, timeout=5,
            )
            if r.status_code != 200:
                continue
            posts = r.json()["data"]["children"]
            for p in posts:
                title = p["data"]["title"]
                # $TICKER mentions (high confidence)
                for m in re.findall(r'\$([A-Z]{2,5})\b', title):
                    tickers[m] = tickers.get(m, 0) + 3
                # Plain uppercase (lower confidence)
                for m in re.findall(r'\b([A-Z]{2,5})\b', title):
                    if m not in NOISE and len(m) >= 2:
                        tickers[m] = tickers.get(m, 0) + 1
        except Exception:
            continue

    return tickers


def get_price_data(ticker):
    """Get price + performance from Yahoo."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": "1y", "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    if r.status_code != 200:
        return None

    data = r.json()
    if data.get("chart", {}).get("error"):
        return None
    result = data["chart"]["result"]
    if not result:
        return None
    result = result[0]

    closes = result["indicators"]["quote"][0]["close"]
    closes = [c for c in closes if c is not None]
    if len(closes) < 50:
        return None

    price = closes[-1]
    perf_1m = (price / closes[-22] - 1) * 100 if len(closes) > 22 else 0
    perf_3m = (price / closes[-66] - 1) * 100 if len(closes) > 66 else 0
    perf_1y = (price / closes[0] - 1) * 100

    return {
        "price": round(price, 2),
        "perf_1m": round(perf_1m, 1),
        "perf_3m": round(perf_3m, 1),
        "perf_1y": round(perf_1y, 1),
    }


def build_hot_picks():
    """Combine signals: analyst (40pts) + momentum (30pts) + reddit (10pts max)."""
    # Get analyst strong buys
    analyst_scores = get_analyst_picks()

    # Get Reddit mentions
    reddit_mentions = get_reddit_mentions()

    # Combine all tickers that appear in any signal
    all_tickers = set(analyst_scores.keys())
    # Only add Reddit tickers if they have 3+ mentions (filter noise)
    reddit_qualified = {t: c for t, c in reddit_mentions.items() if c >= 3}
    all_tickers.update(reddit_qualified.keys())

    if not all_tickers:
        return None, "unreliable", "No data available from any source."

    # Score and fetch price data for top candidates
    results = []
    for ticker in list(all_tickers)[:50]:  # Cap to stay in timeout
        price_data = get_price_data(ticker)
        if not price_data:
            continue

        # Build composite score
        score = 0
        reasons = []

        # Analyst signal (40 pts)
        if ticker in analyst_scores:
            score += 40
            reasons.append("Analyst: Strong Buy")

        # Momentum signal (up to 30 pts)
        if price_data["perf_1m"] > 5:
            score += min(price_data["perf_1m"], 30)
            reasons.append(f"+{price_data['perf_1m']}% this month")

        # Reddit signal (up to 10 pts, capped — unreliable)
        if ticker in reddit_mentions:
            reddit_score = min(reddit_mentions[ticker] * 2, 10)
            score += reddit_score
            reasons.append(f"Reddit buzz ({reddit_mentions[ticker]} mentions)")

        if score > 0:
            results.append({
                "ticker": ticker,
                "price": price_data["price"],
                "score": round(score, 1),
                "perf_1m": price_data["perf_1m"],
                "perf_3m": price_data["perf_3m"],
                "perf_1y": price_data["perf_1y"],
                "reasons": reasons,
            })

    results.sort(key=lambda x: (x["score"], x["perf_1m"]), reverse=True)

    if not results:
        return None, "unreliable", "Could not fetch price data for any candidates."

    return results[:15], "good", None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            stocks, quality, warning = build_hot_picks()

            if quality == "unreliable":
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "stocks": [], "count": 0,
                    "quality": "unreliable", "warning": warning,
                    "strategy": "Hot Picks",
                }).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "stocks": stocks or [],
                "count": len(stocks) if stocks else 0,
                "quality": quality,
                "warning": warning,
                "strategy": "Hot Picks",
                "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "stocks": [], "quality": "error",
                "warning": f"Server error: {str(e)}. Do NOT invest based on this data.",
            }).encode())
