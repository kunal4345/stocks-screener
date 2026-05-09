"""API endpoint: Top Picks — opinionated composite score from 6 factors."""

import json
import re
import requests
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

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


def get_finviz_candidates():
    """Get stocks with Strong Buy + insider buying + good fundamentals."""
    from finvizfinance.screener.financial import Financial

    f = Financial()
    f.set_filter(filters_dict={
        "Market Cap.": "+Mid (over $2bln)",
        "Analyst Recom.": "Buy or better",
        "EPS growththis year": "Positive (>0%)",
        "Return on Equity": "Over +15%",
    })
    df = f.screener_view()
    if df is None or df.empty:
        return {}

    candidates = {}
    for _, row in df.iterrows():
        ticker = row["Ticker"]
        candidates[ticker] = {
            "roe": row.get("ROE", 0),
            "debt_eq": row.get("Debt/Eq", 999),
            "gross_m": row.get("Gross M", 0),
            "earnings": row.get("Earnings", ""),
        }
    return candidates


def get_insider_buys():
    """Get tickers with positive insider transactions."""
    from finvizfinance.screener.overview import Overview

    o = Overview()
    o.set_filter(filters_dict={
        "Market Cap.": "+Mid (over $2bln)",
        "InsiderTransactions": "Positive (>0%)",
        "Analyst Recom.": "Buy or better",
    })
    df = o.screener_view()
    if df is None or df.empty:
        return set()
    return set(df["Ticker"].tolist())


def get_reddit_mentions():
    """Scrape Reddit for ticker mentions."""
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
                for m in re.findall(r'\$([A-Z]{2,5})\b', title):
                    tickers[m] = tickers.get(m, 0) + 3
                for m in re.findall(r'\b([A-Z]{2,5})\b', title):
                    if m not in NOISE and len(m) >= 2:
                        tickers[m] = tickers.get(m, 0) + 1
        except Exception:
            continue
    return tickers


def get_price_data(ticker):
    """Get price + technical signals from Yahoo."""
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
    highs = result["indicators"]["quote"][0]["high"]
    closes = [c for c in closes if c is not None]
    highs = [h for h in highs if h is not None]
    if len(closes) < 50:
        return None

    price = closes[-1]
    high_52w = max(highs) if highs else price
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)
    sma50 = sum(closes[-50:]) / 50

    pct_from_high = (price / high_52w - 1) * 100
    pct_above_200 = (price / sma200 - 1) * 100
    perf_1m = (price / closes[-22] - 1) * 100 if len(closes) > 22 else 0
    perf_1y = (price / closes[0] - 1) * 100

    return {
        "price": round(price, 2),
        "pct_from_high": round(pct_from_high, 1),
        "pct_above_200": round(pct_above_200, 1),
        "above_200": price > sma200,
        "above_50": price > sma50,
        "perf_1m": round(perf_1m, 1),
        "perf_1y": round(perf_1y, 1),
    }


def compute_score(ticker, finviz_data, insider_set, reddit_mentions, price_data):
    """Composite score out of 100. Weights: analyst 25, valuation 20, earnings 15, insider 15, technical 15, reddit 10."""
    score = 0
    reasons = []

    # 1. Analyst (25 pts) — already filtered to Buy or better, give full points
    score += 25
    reasons.append("Analyst: Buy+")

    # 2. Valuation (20 pts) — ROE high + low debt = good value
    roe = finviz_data.get("roe", 0)
    debt = finviz_data.get("debt_eq", 999)
    if isinstance(roe, (int, float)) and roe > 0.20:
        score += 12
    elif isinstance(roe, (int, float)) and roe > 0.15:
        score += 8
    if isinstance(debt, (int, float)) and debt < 1:
        score += 8
        reasons.append("Low debt")
    elif isinstance(debt, (int, float)) and debt < 2:
        score += 4

    # 3. Earnings (15 pts) — upcoming earnings = catalyst
    earnings = finviz_data.get("earnings", "")
    if earnings and "/b" in str(earnings):
        score += 15
        reasons.append("Earnings soon (before market)")
    elif earnings and "/a" in str(earnings):
        score += 15
        reasons.append("Earnings soon (after market)")
    else:
        score += 7  # has positive EPS growth (from filter)

    # 4. Insider buying (15 pts)
    if ticker in insider_set:
        score += 15
        reasons.append("Insiders buying")

    # 5. Technical timing (15 pts) — reward pullbacks, penalize extended
    if price_data["above_200"]:
        pct_from_high = price_data["pct_from_high"]
        if -15 <= pct_from_high <= -5:
            score += 15
            reasons.append(f"Pullback {pct_from_high}% from high")
        elif -5 < pct_from_high <= 0:
            score += 10
            reasons.append("Near highs")
        elif pct_from_high < -15:
            score += 5
            reasons.append(f"Down {pct_from_high}% — deeper dip")
        else:
            score += 8
    else:
        score += 0
        reasons.append("Below 200-day avg ⚠️")

    # 6. Reddit buzz (10 pts max)
    reddit_count = reddit_mentions.get(ticker, 0)
    if reddit_count >= 5:
        score += 10
        reasons.append(f"Trending on Reddit ({reddit_count})")
    elif reddit_count >= 3:
        score += 5
        reasons.append(f"Reddit mentions ({reddit_count})")

    return score, reasons


def build_picks():
    """Build top picks with composite scoring."""
    finviz_candidates = get_finviz_candidates()
    if not finviz_candidates:
        return None, "unreliable", "Finviz returned no candidates."

    insider_set = get_insider_buys()
    reddit_mentions = get_reddit_mentions()

    results = []
    for ticker in list(finviz_candidates.keys())[:60]:
        price_data = get_price_data(ticker)
        if not price_data:
            continue

        score, reasons = compute_score(
            ticker, finviz_candidates[ticker], insider_set, reddit_mentions, price_data
        )

        # Only show if score >= 60
        if score < 60:
            continue

        label = "🟢 Strong Buy" if score >= 80 else "🟡 Buy"

        results.append({
            "ticker": ticker,
            "price": price_data["price"],
            "score": score,
            "label": label,
            "perf_1m": price_data["perf_1m"],
            "perf_1y": price_data["perf_1y"],
            "pct_from_high": price_data["pct_from_high"],
            "reasons": reasons,
        })

    results.sort(key=lambda x: (x["score"], x["perf_1m"]), reverse=True)

    if not results:
        return [], "good", "No stocks scored above 60 right now. Market may be overextended."

    return results[:10], "good", None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            stocks, quality, warning = build_picks()

            if quality == "unreliable":
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "picks": [], "quality": "unreliable", "warning": warning,
                }).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "picks": stocks or [],
                "count": len(stocks) if stocks else 0,
                "quality": quality,
                "warning": warning,
                "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "picks": [], "quality": "error",
                "warning": f"Server error: {str(e)}. Do NOT invest based on this data.",
            }).encode())
