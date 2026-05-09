"""API endpoint: screens entire stock market via Finviz with multiple strategies."""

import json
import os
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
MAX_PRICE_DELTA = 0.05

STRATEGIES = {
    "momentum": {
        "name": "Momentum",
        "desc": "Riding the wave — stocks already ripping higher",
        "filters": {
            "Market Cap.": "+Mid (over $2bln)",
            "EPS growththis year": "Positive (>0%)",
            "Performance": "Year +20%",
            "200-Day Simple Moving Average": "Price above SMA200",
            "50-Day Simple Moving Average": "Price crossed SMA50 above",
        },
    },
    "value": {
        "name": "Value",
        "desc": "Warren Buffett style — cheap, profitable, low debt",
        "filters": {
            "Market Cap.": "+Mid (over $2bln)",
            "P/E": "Under 20",
            "Return on Equity": "Over +15%",
            "Debt/Equity": "Under 1",
            "EPS growththis year": "Positive (>0%)",
        },
    },
    "garp": {
        "name": "GARP",
        "desc": "Peter Lynch style — growing fast but not overpriced",
        "filters": {
            "Market Cap.": "+Large (over $10bln)",
            "PEG": "Under 2",
            "EPS growthnext 5 years": "Over 10%",
            "Sales growthpast 5 years": "Over 10%",
            "EPS growththis year": "Positive (>0%)",
        },
    },
    "dividend": {
        "name": "Dividend",
        "desc": "Passive income — growing dividends you can live off",
        "filters": {
            "Market Cap.": "+Mid (over $2bln)",
            "Dividend Yield": "Over 2%",
            "Payout Ratio": "Under 60%",
            "EPS growthnext 5 years": "Positive (>0%)",
            "Return on Equity": "Over +10%",
        },
    },
    "quality": {
        "name": "Quality",
        "desc": "Best businesses — fat margins, analysts love them",
        "filters": {
            "Market Cap.": "+Large (over $10bln)",
            "Return on Equity": "Over +20%",
            "Gross Margin": "Over 50%",
            "EPS growththis year": "Over 10%",
            "Analyst Recom.": "Buy or better",
        },
    },
}


def screen_finviz(strategy="momentum"):
    """Use Finviz to screen entire market with given strategy filters."""
    from finvizfinance.screener.overview import Overview

    filters = STRATEGIES.get(strategy, STRATEGIES["momentum"])["filters"]
    foverview = Overview()
    foverview.set_filter(filters_dict=filters)
    df = foverview.screener_view()
    if df is None or df.empty:
        return [], {}
    # Return tickers + metadata from Finviz
    meta = {}
    for _, row in df.iterrows():
        meta[row["Ticker"]] = {
            "company": row.get("Company", ""),
            "sector": row.get("Sector", ""),
            "pe": row.get("P/E", 0),
            "market_cap": row.get("Market Cap", 0),
        }
    return df["Ticker"].tolist(), meta


def score_ticker(ticker, strategy="momentum", meta=None):
    """Fetch Yahoo data and score a ticker with strategy-specific reasons."""
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
    timestamps = result.get("timestamp", [])

    if len(closes) < 50:
        return None

    if timestamps:
        last_ts = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
        if (datetime.now(tz=timezone.utc) - last_ts).days > 5:
            return None

    price = closes[-1]
    sma50 = sum(closes[-50:]) / 50
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)

    perf_1m = (price / closes[-22] - 1) * 100 if len(closes) > 22 else 0
    perf_3m = (price / closes[-66] - 1) * 100 if len(closes) > 66 else 0
    perf_1y = (price / closes[0] - 1) * 100

    score = (
        (price / sma200 - 1) * 30 +
        (price / sma50 - 1) * 20 +
        perf_1y * 0.3 +
        perf_3m * 0.2
    )

    # Strategy-specific reasons
    reasons = []
    m = meta or {}
    pe = m.get("pe", 0)

    if strategy == "value":
        if pe and isinstance(pe, (int, float)) and pe > 0:
            reasons.append(f"P/E: {pe:.1f}")
        reasons.append(f"Up {perf_1y:.0f}% YTD")
        if perf_1y > 100:
            reasons.append("⚠️ Extended")
    elif strategy == "dividend":
        if pe and isinstance(pe, (int, float)) and pe > 0:
            reasons.append(f"P/E: {pe:.1f}")
        reasons.append(f"Up {perf_1y:.0f}% YTD")
    elif strategy == "garp":
        if pe and isinstance(pe, (int, float)) and pe > 0:
            reasons.append(f"P/E: {pe:.1f}")
        if perf_1m > 5:
            reasons.append(f"+{perf_1m:.0f}% this month")
        reasons.append(f"Up {perf_1y:.0f}% YTD")
    elif strategy == "quality":
        reasons.append(f"Up {perf_1y:.0f}% YTD")
        if perf_1m > 5:
            reasons.append("Strong momentum")
        if perf_1y > 100:
            reasons.append("⚠️ Extended — verify P/E")
    else:  # momentum
        if perf_1m > 5:
            reasons.append(f"+{perf_1m:.0f}% this month")
        reasons.append(f"Up {perf_1y:.0f}% YTD")
        if perf_1y > 100:
            reasons.append("⚠️ Extended — verify P/E")

    return {
        "ticker": ticker,
        "company": m.get("company", ""),
        "sector": m.get("sector", ""),
        "price": round(price, 2),
        "score": round(score, 2),
        "perf_1m": round(perf_1m, 1),
        "perf_3m": round(perf_3m, 1),
        "perf_1y": round(perf_1y, 1),
        "reasons": reasons,
    }


def screen_stocks(strategy="momentum"):
    """Full pipeline: Finviz screens market → Yahoo scores results."""
    tickers, meta = screen_finviz(strategy)

    if not tickers:
        return None, "unreliable", "Finviz returned no results. Try a different strategy or check back later."

    results = []
    failures = 0
    for ticker in tickers[:60]:  # Cap at 60 to stay within timeout
        try:
            data = score_ticker(ticker, strategy, meta.get(ticker, {}))
            if data:
                results.append(data)
            else:
                failures += 1
        except Exception:
            failures += 1

    total = min(len(tickers), 60)
    if failures > total * 0.5:
        return None, "unreliable", f"Yahoo Finance failing ({failures}/{total} tickers). Do NOT invest based on this data."

    results.sort(key=lambda x: (x["score"], x["perf_1y"]), reverse=True)

    if failures > total * 0.2:
        quality = "degraded"
        warning = f"Partial data: {failures}/{total} tickers failed. Results may be incomplete."
    else:
        quality = "good"
        warning = None

    return results[:15], quality, warning


def cross_validate(stocks):
    """Spot-check prices against Finnhub."""
    if not FINNHUB_KEY or not stocks:
        return None
    check = stocks[:3]
    mismatches = []
    for s in check:
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol={s['ticker']}&token={FINNHUB_KEY}",
                timeout=5,
            )
            if r.status_code != 200:
                continue
            finnhub_price = r.json().get("c", 0)
            if finnhub_price <= 0:
                continue
            delta = abs(s["price"] - finnhub_price) / finnhub_price
            if delta > MAX_PRICE_DELTA:
                mismatches.append(f"{s['ticker']}: Yahoo=${s['price']}, Finnhub=${finnhub_price} ({delta*100:.1f}% off)")
        except Exception:
            continue
    if mismatches:
        return f"Price mismatch: {'; '.join(mismatches)}. Data may be stale."
    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = parse_qs(urlparse(self.path).query)
            strategy = params.get("strategy", ["momentum"])[0]

            if strategy not in STRATEGIES:
                strategy = "momentum"

            stocks, quality, warning = screen_stocks(strategy)

            if quality == "unreliable":
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "stocks": [], "count": 0,
                    "quality": "unreliable", "warning": warning,
                    "strategy": STRATEGIES[strategy]["name"],
                }).encode())
                return

            price_warning = cross_validate(stocks)
            if price_warning:
                quality = "degraded"
                warning = price_warning

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "stocks": stocks or [],
                "count": len(stocks) if stocks else 0,
                "quality": quality,
                "warning": warning,
                "strategy": STRATEGIES[strategy]["name"],
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
